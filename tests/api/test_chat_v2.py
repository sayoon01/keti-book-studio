"""Phase 10b(SessionService) 완료 조건 테스트.

진짜 Ollama 대신 가짜 BaseLlm 구현을 주입해서, ADK의 SessionService가
실제로 대화 맥락(이전 메시지)을 다음 턴 LlmRequest에 넣어주는지,
그리고 우리 get_history_with()가 대화 이력을 제대로 복원하는지 검증한다.
"""

import pytest
from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.chat.adk_runtime import get_history_with, run_chat_turn_with

APP_NAME = "test-app"


class FakeLlm(BaseLlm):
    model: str = "fake-model"
    captured_contents_lengths: list = []
    reply_text: str = "가짜 응답"

    async def generate_content_async(self, llm_request, stream=False):
        type(self).captured_contents_lengths.append(len(llm_request.contents))
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=self.reply_text)])
        )


@pytest.fixture(autouse=True)
def _reset_fake_llm():
    FakeLlm.captured_contents_lengths = []
    yield


def _build_runner(reply_text: str = "가짜 응답"):
    fake_model = FakeLlm(reply_text=reply_text)
    agent = LlmAgent(name="test_chat_agent", model=fake_model, instruction="테스트 에이전트")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    return runner, session_service


@pytest.mark.asyncio
async def test_second_turn_includes_first_turn_in_context():
    runner, session_service = _build_runner()

    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None,
        message="1장 글자수 7천자로 바꿔줘",
    )
    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None,
        message="대상 독자도 초급자로 해줘",
    )

    lengths = FakeLlm.captured_contents_lengths
    assert lengths[0] == 1
    assert lengths[1] > lengths[0]


@pytest.mark.asyncio
async def test_run_chat_turn_returns_final_model_text():
    runner, session_service = _build_runner(reply_text="네, 반영했습니다.")

    answer = await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None,
        message="안녕",
    )
    assert answer == "네, 반영했습니다."


@pytest.mark.asyncio
async def test_get_history_returns_both_turns_in_order():
    runner, session_service = _build_runner(reply_text="응답1")

    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None, message="첫 메시지",
    )

    history = await get_history_with(session_service, APP_NAME, user_id="u1", session_id="s1")
    texts = [h["text"] for h in history]
    assert "첫 메시지" in texts
    assert "응답1" in texts
    assert texts.index("첫 메시지") < texts.index("응답1")


@pytest.mark.asyncio
async def test_different_sessions_do_not_share_memory():
    runner, session_service = _build_runner()

    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="session-A", book_id=None, message="A 대화",
    )
    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="session-B", book_id=None, message="B 대화",
    )

    history_a = await get_history_with(session_service, APP_NAME, user_id="u1", session_id="session-A")
    history_b = await get_history_with(session_service, APP_NAME, user_id="u1", session_id="session-B")

    texts_a = [h["text"] for h in history_a]
    texts_b = [h["text"] for h in history_b]
    assert "A 대화" in texts_a and "A 대화" not in texts_b
    assert "B 대화" in texts_b and "B 대화" not in texts_a


@pytest.mark.asyncio
async def test_get_history_for_nonexistent_session_returns_empty():
    _, session_service = _build_runner()
    history = await get_history_with(
        session_service, APP_NAME, user_id="ghost", session_id="never-created"
    )
    assert history == []


class FakeLlmWithThought(BaseLlm):
    """gemma4:31b 같은 추론 모델이 실제로 내는 형태를 흉내낸다:
    thought=True 파트(추론 과정) + 일반 파트(진짜 답변)를 함께 낸다."""

    model: str = "fake-model-with-thought"

    async def generate_content_async(self, llm_request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text="사용자가 이름을 알려달라고 했다. 답해야 한다.", thought=True),
                    types.Part(text="네, 상아님이라고 기억할게요!"),
                ],
            )
        )


@pytest.mark.asyncio
async def test_run_chat_turn_excludes_thought_parts_from_answer():
    """실전 버그 회귀 테스트: 추론 과정(thought=True)이 사용자 응답에 섞여 나오면 안 된다."""
    agent = LlmAgent(name="test_agent", model=FakeLlmWithThought(), instruction="테스트")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    answer = await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None,
        message="내 이름은 상아야",
    )

    assert answer == "네, 상아님이라고 기억할게요!"
    assert "답해야 한다" not in answer


@pytest.mark.asyncio
async def test_get_history_excludes_thought_parts():
    agent = LlmAgent(name="test_agent", model=FakeLlmWithThought(), instruction="테스트")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    await run_chat_turn_with(
        runner, session_service, APP_NAME,
        user_id="u1", session_id="s1", book_id=None,
        message="내 이름은 상아야",
    )

    history = await get_history_with(session_service, APP_NAME, user_id="u1", session_id="s1")
    texts = [h["text"] for h in history]
    assert any("상아님이라고 기억할게요" in t for t in texts)
    assert not any("답해야 한다" in t for t in texts)
