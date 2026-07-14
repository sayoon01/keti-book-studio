"""Phase 10a(Tracing) 완료 조건 테스트."""

import os
import tempfile
import time

import pytest
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from backend.chat import tracing  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.models import AgentTrace  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    tracing._start_times.clear()
    yield
    SQLModel.metadata.drop_all(engine)


def _query_traces():
    from sqlmodel import select

    with Session(engine) as session:
        return session.exec(select(AgentTrace)).all()


def test_record_trace_writes_row():
    trace = tracing.record_trace(
        session_id="sess-1",
        book_id="book-1",
        event_type="model_call",
        name="gemma4:31b",
        output_summary="안녕하세요",
        latency_ms=123.4,
    )
    assert trace.trace_id.startswith("trace-")

    rows = _query_traces()
    assert len(rows) == 1
    assert rows[0].session_id == "sess-1"
    assert rows[0].output_summary == "안녕하세요"
    assert rows[0].latency_ms == 123.4


def test_record_trace_truncates_long_text():
    long_text = "가" * 3000
    tracing.record_trace(
        session_id="sess-1", event_type="tool_call", name="edit_unit", output_summary=long_text
    )
    rows = _query_traces()
    assert len(rows[0].output_summary) <= 2000


class _FakeSession:
    def __init__(self, session_id):
        self.id = session_id


class _FakeState(dict):
    pass


class _FakeContext:
    def __init__(self, *, agent_name="root_agent", session_id="sess-abc", book_id=None):
        self.agent_name = agent_name
        self.session = _FakeSession(session_id)
        self.state = _FakeState({"book_id": book_id} if book_id else {})
        self.invocation_id = "invocation-1"


class _FakeLlmResponse:
    def __init__(self, content="응답 내용", error_message=None):
        self.content = content
        self.error_message = error_message


class _FakeTool:
    def __init__(self, name):
        self.name = name


def test_model_callback_pair_records_latency_and_output():
    ctx = _FakeContext(book_id="book-42")

    tracing.before_model_callback(ctx, llm_request=None)
    time.sleep(0.01)
    result = tracing.after_model_callback(ctx, _FakeLlmResponse(content="1장 글자수를 바꿨습니다"))

    assert result is None

    rows = _query_traces()
    assert len(rows) == 1
    assert rows[0].event_type == "model_call"
    assert rows[0].name == "root_agent"
    assert rows[0].book_id == "book-42"
    assert rows[0].output_summary == "1장 글자수를 바꿨습니다"
    assert rows[0].latency_ms is not None and rows[0].latency_ms > 0


def test_model_callback_records_error():
    ctx = _FakeContext()
    tracing.before_model_callback(ctx, llm_request=None)
    tracing.after_model_callback(ctx, _FakeLlmResponse(content="", error_message="timeout"))

    rows = _query_traces()
    assert rows[0].error == "timeout"


def test_tool_callback_pair_records_args_and_response():
    ctx = _FakeContext(session_id="sess-tool")
    tool = _FakeTool("edit_unit")
    args = {"book_id": "book-99", "unit_id": "unit-1", "target_characters": 7000}

    tracing.before_tool_callback(tool, args, ctx)
    time.sleep(0.01)
    tracing.after_tool_callback(tool, args, ctx, {"status": "ok"})

    rows = _query_traces()
    assert len(rows) == 1
    assert rows[0].event_type == "tool_call"
    assert rows[0].name == "edit_unit"
    assert rows[0].book_id == "book-99"
    assert "7000" in rows[0].input_summary
    assert "ok" in rows[0].output_summary
    assert rows[0].latency_ms is not None and rows[0].latency_ms > 0


def test_timer_keys_do_not_collide_across_different_contexts():
    ctx_a = _FakeContext(session_id="sess-a")
    ctx_a.invocation_id = "invocation-a"
    ctx_b = _FakeContext(session_id="sess-b")
    ctx_b.invocation_id = "invocation-b"

    tracing.before_model_callback(ctx_a, llm_request=None)
    tracing.before_model_callback(ctx_b, llm_request=None)

    assert len(tracing._start_times) == 2

    tracing.after_model_callback(ctx_a, _FakeLlmResponse())
    assert len(tracing._start_times) == 1

    tracing.after_model_callback(ctx_b, _FakeLlmResponse())
    assert len(tracing._start_times) == 0
