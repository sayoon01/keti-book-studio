"""Function calling 버전의 승인 게이트.

Phase 7의 ActionPlan/approval_policy를 그대로 재사용한다. before_tool_callback이
승인이 필요하면 실제 도구 실행을 건너뛰고 ActionPlan(status="pending")만
만들어서 반환한다. 이렇게 만들어진 ActionPlan은 기존 POST /api/actions/{id}/approve
로 그대로 승인 처리된다.
"""

from sqlmodel import Session, select

from backend.chat.approval_policy import needs_approval
from backend.chat.tool_actions import (
    MUTATING_TOOLS,
    TOOL_TO_ACTION,
    TOOL_TO_TARGET_TYPE,
    build_patch,
    resolve_target_id,
)
from backend.storage.database import engine
from backend.storage.models import ActionPlan, BookConfig


def _get_approval_mode(session: Session, book_id: str) -> str:
    config = session.exec(select(BookConfig).where(BookConfig.book_id == book_id)).first()
    return config.approval_mode if config else "balanced"


def approval_gate_callback(tool, args, tool_context):
    if tool.name not in MUTATING_TOOLS:
        return None

    book_id = tool_context.state.get("book_id") if tool_context.state else None
    if not book_id:
        return {"error": "현재 대화에 연결된 책이 없습니다. book_id가 세션에 없습니다."}

    with Session(engine) as session:
        target_id = resolve_target_id(session, tool.name, book_id, args)
        if target_id is None:
            return {"error": f"작업 대상을 찾을 수 없습니다 (tool={tool.name}, args={args})."}

        approval_mode = _get_approval_mode(session, book_id)
        action_name = TOOL_TO_ACTION[tool.name]
        if not needs_approval(action_name, approval_mode):
            return None

        patch = build_patch(tool.name, args)
        action = ActionPlan(
            book_id=book_id,
            action=action_name,
            target_type=TOOL_TO_TARGET_TYPE[tool.name],
            target_id=target_id,
            patch=patch,
            summary=f"{action_name}: {patch or args}",
            status="pending",
        )
        session.add(action)
        session.commit()
        session.refresh(action)

        return {
            "status": "pending_approval",
            "action_id": action.action_id,
            "summary": action.summary,
            "message": "사용자 승인이 필요합니다. 승인 전까지는 반영되지 않았다고 안내하세요.",
        }
