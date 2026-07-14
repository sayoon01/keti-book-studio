"""Phase 10c(Function Calling) 완료 조건 테스트.

1. tool_actions.build_patch/resolve_unit_id 순수 함수 검증
2. approval_gate_callback: auto 모드면 통과(None), balanced/safe면 ActionPlan 생성
3. approve_outline_tool/generate_outline_tool은 auto 모드여도 항상 승인 필요
4. 도구 함수 직접 호출(ADK Runner 없이): auto 모드에서 실제로 DB가 바뀌는지
5. 승인 후 기존 POST /api/actions/{id}/approve 로 반영되는지
   (v1 채팅과 v2 채팅이 완전히 같은 승인 처리 경로를 공유한다는 증거)
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["KETI_PERSONA_DIR"] = tempfile.mkdtemp()

from backend.chat import tool_actions  # noqa: E402
from backend.chat.adk_tools import (  # noqa: E402
    edit_config_tool,
    edit_unit_tool,
    get_book_overview_tool,
    get_chapter_tool,
)
from backend.chat.approval_gate import approval_gate_callback  # noqa: E402
from backend.main import app  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.models import ActionPlan  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


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
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 기술서"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    unit = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장. 개요", "target_characters": 5000},
    ).json()
    return {"book": book, "outline": outline, "unit": unit}


class _FakeToolContext:
    def __init__(self, book_id):
        self.state = {"book_id": book_id} if book_id else {}


class _FakeTool:
    def __init__(self, name):
        self.name = name


def test_build_patch_filters_empty_and_zero_values():
    patch = tool_actions.build_patch(
        "edit_unit_tool",
        {"title": "", "description": "새 설명", "target_characters": 0, "custom_instructions": ""},
    )
    assert patch == {"description": "새 설명"}


def test_build_patch_keeps_nonzero_numeric_fields():
    patch = tool_actions.build_patch(
        "edit_config_tool",
        {"document_type": "", "default_chars_per_chapter": 6000, "tone": "친근하게"},
    )
    assert patch == {"default_chars_per_chapter": 6000, "tone": "친근하게"}


def test_resolve_unit_id_finds_correct_unit(client):
    ctx = _create_book_with_unit(client)
    with Session(engine) as session:
        unit_id = tool_actions.resolve_unit_id(session, ctx["book"]["book_id"], 1)
        assert unit_id == ctx["unit"]["unit_id"]
        assert tool_actions.resolve_unit_id(session, ctx["book"]["book_id"], 99) is None


def test_approval_gate_passes_through_in_auto_mode(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})

    result = approval_gate_callback(
        _FakeTool("edit_unit_tool"),
        {"chapter_number": 1, "target_characters": 7000},
        _FakeToolContext(ctx["book"]["book_id"]),
    )
    assert result is None


def test_approval_gate_creates_action_plan_in_balanced_mode(client):
    ctx = _create_book_with_unit(client)

    result = approval_gate_callback(
        _FakeTool("edit_unit_tool"),
        {"chapter_number": 1, "target_characters": 7000},
        _FakeToolContext(ctx["book"]["book_id"]),
    )
    assert result["status"] == "pending_approval"
    assert "action_id" in result

    with Session(engine) as session:
        action = session.get(ActionPlan, result["action_id"])
        assert action.action == "edit_unit"
        assert action.patch == {"target_characters": 7000}
        assert action.status == "pending"


def test_approval_gate_always_requires_approval_for_generate_outline_even_auto(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})

    result = approval_gate_callback(
        _FakeTool("generate_outline_tool"), {}, _FakeToolContext(ctx["book"]["book_id"])
    )
    assert result["status"] == "pending_approval"


def test_approval_gate_missing_book_id_returns_error():
    result = approval_gate_callback(_FakeTool("edit_unit_tool"), {"chapter_number": 1}, _FakeToolContext(None))
    assert "error" in result


def test_approval_gate_unresolvable_chapter_returns_error(client):
    ctx = _create_book_with_unit(client)
    result = approval_gate_callback(
        _FakeTool("edit_unit_tool"),
        {"chapter_number": 99, "target_characters": 7000},
        _FakeToolContext(ctx["book"]["book_id"]),
    )
    assert "error" in result


def test_edit_unit_tool_executes_immediately_and_recalculates_config(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})

    result = edit_unit_tool(
        tool_context=_FakeToolContext(ctx["book"]["book_id"]),
        chapter_number=1,
        target_characters=7000,
    )
    assert result["target_characters"] == 7000

    config = client.get(f"/api/books/{ctx['book']['book_id']}/config").json()
    assert config["total_target_characters"] == 7000


def test_edit_config_tool_executes_immediately(client):
    ctx = _create_book_with_unit(client)

    result = edit_config_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]), tone="친근하게")
    assert result["tone"] == "친근하게"


def test_edit_unit_tool_without_book_id_returns_error():
    result = edit_unit_tool(tool_context=_FakeToolContext(None), chapter_number=1, target_characters=7000)
    assert "error" in result


def test_edit_config_tool_with_no_fields_returns_error(client):
    ctx = _create_book_with_unit(client)
    result = edit_config_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]))
    assert "error" in result


def test_pending_action_plan_can_be_approved_via_existing_v1_endpoint(client):
    ctx = _create_book_with_unit(client)

    gate_result = approval_gate_callback(
        _FakeTool("edit_unit_tool"),
        {"chapter_number": 1, "target_characters": 8000},
        _FakeToolContext(ctx["book"]["book_id"]),
    )
    action_id = gate_result["action_id"]

    outline_before = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_before["units"][0]["target_characters"] == 5000

    approve_resp = client.post(f"/api/actions/{action_id}/approve")
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["result"]["target_characters"] == 8000

    outline_after = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_after["units"][0]["target_characters"] == 8000


# ---------------------------------------------------------------------------
# 읽기 전용 도구 (승인 게이트 대상 아님, 항상 즉시 실행)
# ---------------------------------------------------------------------------
def test_get_book_overview_tool_returns_summary_with_chapters(client):
    ctx = _create_book_with_unit(client)

    result = get_book_overview_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]))

    assert result["title"] == "ALD 기술서"
    assert result["config"]["approval_mode"] == "balanced"
    assert len(result["chapters"]) == 1
    assert result["chapters"][0]["chapter_number"] == 1
    assert result["chapters"][0]["has_body"] is False
    assert result["pending_approvals"] == []


def test_get_book_overview_tool_lists_pending_approvals(client):
    ctx = _create_book_with_unit(client)

    approval_gate_callback(
        _FakeTool("edit_unit_tool"),
        {"chapter_number": 1, "target_characters": 9000},
        _FakeToolContext(ctx["book"]["book_id"]),
    )

    result = get_book_overview_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]))
    assert len(result["pending_approvals"]) == 1
    assert result["pending_approvals"][0]["action"] == "edit_unit"
    assert result["chapters"][0]["target_characters"] == 5000


def test_get_book_overview_tool_without_book_id_returns_error():
    result = get_book_overview_tool(tool_context=_FakeToolContext(None))
    assert "error" in result


def test_get_chapter_tool_returns_detail(client):
    ctx = _create_book_with_unit(client)

    result = get_chapter_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]), chapter_number=1)
    assert result["title"] == "1장. 개요"
    assert result["target_characters"] == 5000
    assert result["has_body"] is False
    assert result["body_preview"] is None


def test_get_chapter_tool_unresolvable_chapter_returns_error(client):
    ctx = _create_book_with_unit(client)
    result = get_chapter_tool(tool_context=_FakeToolContext(ctx["book"]["book_id"]), chapter_number=99)
    assert "error" in result


def test_read_only_tools_are_not_gated_by_approval():
    assert "get_book_overview_tool" not in tool_actions.MUTATING_TOOLS
    assert "get_chapter_tool" not in tool_actions.MUTATING_TOOLS

    result = approval_gate_callback(
        _FakeTool("get_book_overview_tool"), {}, _FakeToolContext("book-whatever")
    )
    assert result is None
