"""Function calling 도구.

여기서 실행 로직을 새로 만들지 않는다. Phase 7의 chat._execute_action()과
chat._serialize_result()를 그대로 재사용한다 — 폼/채팅v1/채팅v2가 전부 같은
실행 경로를 타게 하기 위함.

변경 도구(edit_config_tool 등)는 approval_gate_callback이 None을 반환했을
때(=승인 불필요)만 실제로 호출된다. 읽기 전용 도구(get_book_overview_tool 등)는
MUTATING_TOOLS에 없으므로 승인 게이트를 아예 거치지 않고 항상 즉시 실행된다.

tool_context 파라미터는 ADK가 자동으로 주입한다(LLM에게 노출되는 스키마에서는
빠진다) — 세션 상태(book_id)를 읽는 용도로만 쓴다.
"""

from fastapi import HTTPException
from google.adk.tools import ToolContext
from sqlmodel import Session, select

from backend.api.chat import _execute_action, _serialize_result
from backend.chat.tool_actions import build_patch, resolve_unit_id
from backend.services.llm_client import (
    get_llm_call,
    get_reviewer_llm_call,
    get_reviser_llm_call,
    get_writer_llm_call,
)
from backend.storage.database import engine
from backend.storage.models import ActionPlan, BookConfig, BookOutline, BookProject, BookUnit


def _run(
    session: Session,
    action: str,
    target_id: str,
    patch: dict,
    *,
    writer_llm=None,
    reviewer_llm=None,
    reviser_llm=None,
    outline_llm=None,
) -> dict:
    try:
        result = _execute_action(
            session, action, target_id, patch,
            writer_llm=writer_llm, reviewer_llm=reviewer_llm,
            reviser_llm=reviser_llm, outline_llm=outline_llm,
        )
    except HTTPException as exc:
        return {"error": exc.detail}
    return _serialize_result(session, result)


def edit_config_tool(
    tool_context: ToolContext,
    document_type: str = "",
    target_reader: str = "",
    purpose: str = "",
    tone: str = "",
    expertise_level: str = "",
    default_chars_per_chapter: int = 0,
    citation_policy: str = "",
    visual_density: str = "",
    approval_mode: str = "",
) -> dict:
    """책 설정(대상 독자, 문체, 전문성 수준, 인용 정책, 시각자료 밀도, 승인 모드 등)을
    변경한다. 사용자가 실제로 언급한 항목만 값을 채우고, 언급하지 않은 항목은
    빈 문자열("") 또는 0으로 그대로 두세요."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    patch = build_patch(
        "edit_config_tool",
        {
            "document_type": document_type,
            "target_reader": target_reader,
            "purpose": purpose,
            "tone": tone,
            "expertise_level": expertise_level,
            "default_chars_per_chapter": default_chars_per_chapter,
            "citation_policy": citation_policy,
            "visual_density": visual_density,
            "approval_mode": approval_mode,
        },
    )
    if not patch:
        return {"error": "변경할 항목이 없습니다. 최소 한 개 필드는 채워주세요."}

    with Session(engine) as session:
        return _run(session, "edit_config", book_id, patch)


def edit_unit_tool(
    tool_context: ToolContext,
    chapter_number: int,
    title: str = "",
    description: str = "",
    target_characters: int = 0,
    custom_instructions: str = "",
) -> dict:
    """해당 번호(1부터 시작)의 챕터 제목/설명/목표 글자수/추가 지침을 변경한다.
    사용자가 실제로 언급한 항목만 값을 채우세요."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        unit_id = resolve_unit_id(session, book_id, chapter_number)
        if not unit_id:
            return {"error": f"{chapter_number}번째 챕터를 찾을 수 없습니다."}

        patch = build_patch(
            "edit_unit_tool",
            {
                "title": title,
                "description": description,
                "target_characters": target_characters,
                "custom_instructions": custom_instructions,
            },
        )
        if not patch:
            return {"error": "변경할 항목이 없습니다. 최소 한 개 필드는 채워주세요."}

        return _run(session, "edit_unit", unit_id, patch)


def generate_outline_tool(tool_context: ToolContext, chapter_count: int = 0) -> dict:
    """목차를 새로 생성한다. 기존 목차는 전부 대체되니, 사용자가 확실히
    원할 때만 호출하세요. chapter_count 를 지정 안 하면 기본값(8)을 쓴다."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        return _run(
            session, "generate_outline", book_id, {},
            outline_llm=get_llm_call(),
        )


def approve_outline_tool(tool_context: ToolContext) -> dict:
    """현재 목차를 승인한다. 승인 후에만 챕터 본문 집필을 시작할 수 있다."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        return _run(session, "approve_outline", book_id, {})


def generate_chapter_tool(tool_context: ToolContext, chapter_number: int) -> dict:
    """해당 번호(1부터 시작)의 챕터 본문을 새로 쓴다(이미 있으면 다시 쓴다).
    목차가 승인된 상태여야 하고, 시간이 걸릴 수 있다고 사용자에게 미리 안내하세요."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        unit_id = resolve_unit_id(session, book_id, chapter_number)
        if not unit_id:
            return {"error": f"{chapter_number}번째 챕터를 찾을 수 없습니다."}

        return _run(
            session, "generate_chapter", unit_id, {},
            writer_llm=get_writer_llm_call(),
            reviewer_llm=get_reviewer_llm_call(),
            reviser_llm=get_reviser_llm_call(),
            outline_llm=None,
        )


# ---------------------------------------------------------------------------
# 읽기 전용 도구 (승인 게이트 대상 아님 — MUTATING_TOOLS에 없으므로 항상 즉시 실행)
#
# 목적: 모델이 "승인했다"는 사용자 말을 무조건 믿지 않고, 실제 DB 상태(특히
# 승인 대기 중인 작업이 남아있는지)를 직접 확인할 수 있게 한다.
# ---------------------------------------------------------------------------
def get_book_overview_tool(tool_context: ToolContext) -> dict:
    """현재 대화 중인 책의 전체 상태를 조회한다: 설정 요약, 목차 상태,
    챕터별 진행 상태, 승인 대기 중인 작업 목록. 사용자가 "승인했다",
    "다 됐다" 같은 말을 해도 그대로 믿지 말고 이 도구로 실제 상태를 먼저
    확인한 뒤 답하세요."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        book = session.get(BookProject, book_id)
        if not book:
            return {"error": "책을 찾을 수 없습니다."}

        config = session.exec(select(BookConfig).where(BookConfig.book_id == book_id)).first()
        outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()

        units = []
        if outline:
            units = session.exec(
                select(BookUnit)
                .where(BookUnit.outline_id == outline.outline_id)
                .order_by(BookUnit.order)
            ).all()

        pending = session.exec(
            select(ActionPlan).where(ActionPlan.book_id == book_id, ActionPlan.status == "pending")
        ).all()

        return {
            "title": book.title,
            "config": {
                "document_type": config.document_type if config else None,
                "target_reader": config.target_reader if config else None,
                "tone": config.tone if config else None,
                "approval_mode": config.approval_mode if config else None,
                "total_target_characters": config.total_target_characters if config else 0,
                "chapter_count": config.chapter_count if config else 0,
            },
            "outline_status": outline.status if outline else None,
            "chapters": [
                {
                    "chapter_number": u.order,
                    "title": u.title,
                    "target_characters": u.target_characters,
                    "status": u.status,
                    "has_body": bool(u.body_md),
                }
                for u in units
            ],
            "pending_approvals": [
                {"action_id": a.action_id, "action": a.action, "summary": a.summary}
                for a in pending
            ],
        }


def get_chapter_tool(tool_context: ToolContext, chapter_number: int) -> dict:
    """특정 챕터(번호로 지정, 1부터 시작)의 상세 상태를 조회한다: 제목, 설명,
    목표 글자수, 필수 포함 내용, 진행 상태, 본문 작성 여부와 미리보기."""
    book_id = tool_context.state.get("book_id")
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다."}

    with Session(engine) as session:
        unit_id = resolve_unit_id(session, book_id, chapter_number)
        if not unit_id:
            return {"error": f"{chapter_number}번째 챕터를 찾을 수 없습니다."}

        unit = session.get(BookUnit, unit_id)
        body_preview = None
        if unit.body_md:
            body_preview = unit.body_md[:200] + ("..." if len(unit.body_md) > 200 else "")

        return {
            "chapter_number": unit.order,
            "title": unit.title,
            "description": unit.description,
            "target_characters": unit.target_characters,
            "must_cover": unit.must_cover,
            "status": unit.status,
            "has_body": bool(unit.body_md),
            "body_version": unit.body_version,
            "body_preview": body_preview,
        }
