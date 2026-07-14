"""Function calling 도구(5개)와 승인 게이트가 공유하는 헬퍼.

핵심: patch 조립 로직과 대상 ID 해석 로직을 여기 한 곳에만 두고,
approval_gate.py(승인 필요 시 ActionPlan에 저장)와 adk_tools.py(즉시 실행 시
실제로 호출)가 똑같은 함수를 써서 patch/target_id를 만든다 — 두 경로가
서로 다른 결과를 내는 걸 방지하기 위함.
"""

from typing import Optional

from sqlmodel import Session, select

from backend.storage.models import BookOutline, BookUnit

MUTATING_TOOLS = {
    "edit_config_tool",
    "edit_unit_tool",
    "generate_outline_tool",
    "approve_outline_tool",
    "generate_chapter_tool",
}

TOOL_TO_ACTION = {
    "edit_config_tool": "edit_config",
    "edit_unit_tool": "edit_unit",
    "generate_outline_tool": "generate_outline",
    "approve_outline_tool": "approve_outline",
    "generate_chapter_tool": "generate_chapter",
}

TOOL_TO_TARGET_TYPE = {
    "edit_config_tool": "BookConfig",
    "edit_unit_tool": "BookUnit",
    "generate_outline_tool": "BookOutline",
    "approve_outline_tool": "BookOutline",
    "generate_chapter_tool": "BookUnit",
}


def _clean_patch(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if v not in ("", 0, None)}


def build_patch(tool_name: str, args: dict) -> dict:
    if tool_name == "edit_config_tool":
        return _clean_patch(
            {
                "document_type": args.get("document_type", ""),
                "target_reader": args.get("target_reader", ""),
                "purpose": args.get("purpose", ""),
                "tone": args.get("tone", ""),
                "expertise_level": args.get("expertise_level", ""),
                "default_chars_per_chapter": args.get("default_chars_per_chapter", 0),
                "citation_policy": args.get("citation_policy", ""),
                "visual_density": args.get("visual_density", ""),
                "approval_mode": args.get("approval_mode", ""),
            }
        )
    if tool_name == "edit_unit_tool":
        return _clean_patch(
            {
                "title": args.get("title", ""),
                "description": args.get("description", ""),
                "target_characters": args.get("target_characters", 0),
                "custom_instructions": args.get("custom_instructions", ""),
            }
        )
    return {}


def resolve_unit_id(session: Session, book_id: str, chapter_number: int) -> Optional[str]:
    outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()
    if not outline:
        return None
    unit = session.exec(
        select(BookUnit).where(
            BookUnit.outline_id == outline.outline_id, BookUnit.order == chapter_number
        )
    ).first()
    return unit.unit_id if unit else None


def resolve_target_id(session: Session, tool_name: str, book_id: str, args: dict) -> Optional[str]:
    if tool_name in ("edit_config_tool", "generate_outline_tool", "approve_outline_tool"):
        return book_id
    if tool_name in ("edit_unit_tool", "generate_chapter_tool"):
        chapter_number = args.get("chapter_number")
        if chapter_number is None:
            return None
        return resolve_unit_id(session, book_id, chapter_number)
    return None
