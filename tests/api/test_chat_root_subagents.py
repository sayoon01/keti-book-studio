"""Phase 10c-Step3(ChatRoot + Sub-agents) 완료 조건 테스트.

가짜 모델로 실제 Runner를 돌려서 "루트가 transfer_to_agent로 위임 -> 서브가
도구를 실행"이 진짜로 되는지 검증한다. 승인 게이트가 서브 에이전트 레벨에서도
그대로 걸리는지(콜백이 에이전트별로 독립이라 놓치기 쉬운 부분)도 확인한다.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["KETI_PERSONA_DIR"] = tempfile.mkdtemp()

from backend.chat.adk_agent import ROOT_INSTRUCTION, build_chat_agent  # noqa: E402
from backend.chat.adk_tools import get_book_overview_tool, get_chapter_tool  # noqa: E402
from backend.chat.sub_agents.editor_agent import build_editor_agent  # noqa: E402
from backend.chat.sub_agents.outline_agent import build_outline_agent  # noqa: E402
from backend.chat.sub_agents.writing_agent import build_writing_agent  # noqa: E402
from backend.chat.tracing import (  # noqa: E402
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)
from backend.main import app  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402

APP_NAME = "test-app"


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book_with_unit(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "위임 테스트"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    unit = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장", "target_characters": 5000},
    ).json()
    return {"book": book, "outline": outline, "unit": unit}


def test_build_chat_agent_has_expected_sub_agent_tree():
    class DummyLlm(BaseLlm):
        model: str = "dummy"

        async def generate_content_async(self, llm_request, stream=False):
            yield LlmResponse()

    root = build_chat_agent(model=DummyLlm())

    assert root.name == "book_studio_root"
    assert {t.name for t in root.tools} == {"get_book_overview_tool", "get_chapter_tool"}

    sub_names = {a.name for a in root.sub_agents}
    assert sub_names == {"editor_agent", "outline_agent", "writing_agent"}

    editor = next(a for a in root.sub_agents if a.name == "editor_agent")
    assert {t.name for t in editor.tools} == {"edit_config_tool", "edit_unit_tool"}

    outline_agent = next(a for a in root.sub_agents if a.name == "outline_agent")
    assert {t.name for t in outline_agent.tools} == {"generate_outline_tool", "approve_outline_tool"}

    writing_agent = next(a for a in root.sub_agents if a.name == "writing_agent")
    assert {t.name for t in writing_agent.tools} == {"generate_chapter_tool"}


def _build_root_with_fakes(root_model, editor_model, outline_model=None, writing_model=None):
    editor = build_editor_agent(editor_model)
    outline_agent = build_outline_agent(outline_model or editor_model)
    writing_agent = build_writing_agent(writing_model or editor_model)

    root = LlmAgent(
        name="book_studio_root",
        model=root_model,
        description="root",
        instruction=ROOT_INSTRUCTION,
        tools=[FunctionTool(get_book_overview_tool), FunctionTool(get_chapter_tool)],
        sub_agents=[editor, outline_agent, writing_agent],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )
    return root


class _TransferThenToolLlm(BaseLlm):
    model: str = "fake-router"
    target_agent: str = "editor_agent"

    async def generate_content_async(self, llm_request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="transfer_to_agent", args={"agent_name": self.target_agent}
                        )
                    )
                ],
            )
        )


class _ToolThenTextLlm(BaseLlm):
    model: str = "fake-sub"
    tool_name: str = "edit_unit_tool"
    tool_args: dict = {}
    reply_text: str = "완료했습니다."
    call_count: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        type(self).call_count += 1
        if type(self).call_count == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(name=self.tool_name, args=self.tool_args)
                        )
                    ],
                )
            )
        else:
            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=self.reply_text)])
            )


@pytest.mark.asyncio
async def test_root_delegates_and_executes_immediately_in_auto_mode(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})

    _ToolThenTextLlm.call_count = 0
    editor_llm = _ToolThenTextLlm(
        tool_name="edit_unit_tool",
        tool_args={"chapter_number": 1, "target_characters": 7500},
        reply_text="1장 글자수를 7500자로 바꿨습니다.",
    )
    root = _build_root_with_fakes(_TransferThenToolLlm(), editor_llm)

    session_service = InMemorySessionService()
    runner = Runner(agent=root, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(
        app_name=APP_NAME, user_id="u1", session_id="s1", state={"book_id": ctx["book"]["book_id"]}
    )

    final_text = ""
    async for event in runner.run_async(
        user_id="u1", session_id="s1",
        new_message=types.Content(role="user", parts=[types.Part(text="1장 글자수 7500자로 바꿔줘")]),
    ):
        if event.content and event.content.parts:
            texts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if texts:
                final_text = "".join(texts)

    assert "7500" in final_text

    config = client.get(f"/api/books/{ctx['book']['book_id']}/config").json()
    assert config["total_target_characters"] == 7500


@pytest.mark.asyncio
async def test_root_delegates_and_creates_pending_approval_in_balanced_mode(client):
    ctx = _create_book_with_unit(client)

    _ToolThenTextLlm.call_count = 0
    editor_llm = _ToolThenTextLlm(
        tool_name="edit_unit_tool",
        tool_args={"chapter_number": 1, "target_characters": 9000},
        reply_text="승인이 필요합니다.",
    )
    root = _build_root_with_fakes(_TransferThenToolLlm(), editor_llm)

    session_service = InMemorySessionService()
    runner = Runner(agent=root, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(
        app_name=APP_NAME, user_id="u1", session_id="s1", state={"book_id": ctx["book"]["book_id"]}
    )

    tool_response = None
    async for event in runner.run_async(
        user_id="u1", session_id="s1",
        new_message=types.Content(role="user", parts=[types.Part(text="1장 글자수 9천자로 바꿔줘")]),
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if getattr(p, "function_response", None) and p.function_response.name == "edit_unit_tool":
                    tool_response = p.function_response.response

    assert tool_response["status"] == "pending_approval"
    action_id = tool_response["action_id"]

    config_before = client.get(f"/api/books/{ctx['book']['book_id']}/config").json()
    assert config_before["total_target_characters"] == 5000

    approve_resp = client.post(f"/api/actions/{action_id}/approve")
    assert approve_resp.status_code == 200, approve_resp.text

    config_after = client.get(f"/api/books/{ctx['book']['book_id']}/config").json()
    assert config_after["total_target_characters"] == 9000
