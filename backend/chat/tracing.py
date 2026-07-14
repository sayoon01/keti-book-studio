"""ADK 콜백 기반 실행 추적.

콜백 자체(before_model_callback 등)는 ADK Context/LlmRequest/LlmResponse에서
필요한 값만 뽑아 넘기는 얇은 어댑터로만 두고, 실제 기록 로직은 record_trace()라는
순수 함수로 분리한다 — 진짜 ADK 객체를 만들지 않고도(Runner 없이도) 단위 테스트가
가능하게 하기 위함.
"""

import time
from typing import Optional

from sqlmodel import Session

from backend.storage.database import engine
from backend.storage.models import AgentTrace

_start_times: dict[str, float] = {}


def _truncate(value, limit: int = 500) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def record_trace(
    *,
    session_id: str,
    book_id: Optional[str] = None,
    event_type: str,
    name: str,
    input_summary: str = "",
    output_summary: str = "",
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
) -> AgentTrace:
    with Session(engine) as session:
        trace = AgentTrace(
            session_id=session_id,
            book_id=book_id,
            event_type=event_type,
            name=name,
            input_summary=_truncate(input_summary, 2000),
            output_summary=_truncate(output_summary, 2000),
            latency_ms=latency_ms,
            error=error,
        )
        session.add(trace)
        session.commit()
        session.refresh(trace)
        return trace


def _timer_key(context, kind: str) -> str:
    invocation_id = getattr(context, "invocation_id", None) or id(context)
    return f"{invocation_id}:{kind}"


def _session_id_of(context) -> str:
    session = getattr(context, "session", None)
    return getattr(session, "id", "unknown-session") if session else "unknown-session"


def _book_id_of(context) -> Optional[str]:
    state = getattr(context, "state", None)
    if state is None:
        return None
    try:
        return state.get("book_id")
    except Exception:
        return None


def before_model_callback(callback_context, llm_request):
    _start_times[_timer_key(callback_context, "model")] = time.monotonic()
    return None  # 요청을 가로채지 않고 그냥 통과시킨다


def after_model_callback(callback_context, llm_response):
    start = _start_times.pop(_timer_key(callback_context, "model"), None)
    latency_ms = (time.monotonic() - start) * 1000 if start is not None else None

    output_text = ""
    error = None
    if llm_response is not None:
        error = getattr(llm_response, "error_message", None)
        content = getattr(llm_response, "content", None)
        if content is not None:
            output_text = str(content)

    record_trace(
        session_id=_session_id_of(callback_context),
        book_id=_book_id_of(callback_context),
        event_type="model_call",
        name=getattr(callback_context, "agent_name", "unknown"),
        output_summary=output_text,
        latency_ms=latency_ms,
        error=error,
    )
    return None


def before_tool_callback(tool, args, tool_context):
    _start_times[_timer_key(tool_context, f"tool:{getattr(tool, 'name', 'unknown')}")] = time.monotonic()
    return None


def after_tool_callback(tool, args, tool_context, tool_response):
    tool_name = getattr(tool, "name", "unknown")
    start = _start_times.pop(_timer_key(tool_context, f"tool:{tool_name}"), None)
    latency_ms = (time.monotonic() - start) * 1000 if start is not None else None

    book_id = args.get("book_id") if isinstance(args, dict) else None

    record_trace(
        session_id=_session_id_of(tool_context),
        book_id=book_id or _book_id_of(tool_context),
        event_type="tool_call",
        name=tool_name,
        input_summary=str(args),
        output_summary=str(tool_response),
        latency_ms=latency_ms,
    )
    return None
