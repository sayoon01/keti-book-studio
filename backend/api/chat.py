import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.agents.field_extractor import extract_config_patch, extract_unit_patch
from backend.agents.intent_classifier import classify_intent
from backend.agents.qa_agent import answer_question
from backend.api import config as config_api
from backend.api import outlines as outlines_api
from backend.api import units as units_api
from backend.chat.approval_policy import needs_approval
from backend.services.llm_client import (
    get_llm_call,
    get_reviewer_llm_call,
    get_reviser_llm_call,
    get_writer_llm_call,
)
from backend.storage.database import get_session
from backend.storage.models import (
    ActionPlan,
    BookConfig,
    BookConfigUpdate,
    BookOutline,
    BookProject,
    BookUnit,
    BookUnitUpdate,
    SourceDocument,
    SourceProfile,
)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    book_id: str
    message: str
    scope_type: str = "general"
    scope_id: Optional[str] = None


def _resolve_unit_id(
    session: Session, book_id: str, message: str, scope_type: str, scope_id: Optional[str]
) -> Optional[str]:
    if scope_type == "unit" and scope_id:
        return scope_id

    match = re.search(r"(\d+)\s*장", message)
    if not match:
        return None
    order = int(match.group(1))

    outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()
    if not outline:
        return None
    unit = session.exec(
        select(BookUnit).where(BookUnit.outline_id == outline.outline_id, BookUnit.order == order)
    ).first()
    return unit.unit_id if unit else None


def _execute_action(
    session: Session,
    action: str,
    target_id: str,
    patch: dict,
    *,
    writer_llm,
    reviewer_llm,
    reviser_llm,
    outline_llm,
):
    if action == "edit_config":
        return config_api.update_config(target_id, BookConfigUpdate(**patch), session)

    if action == "edit_unit":
        unit = session.get(BookUnit, target_id)
        if not unit:
            raise HTTPException(404, "unit not found")
        return units_api.update_unit(unit.outline_id, target_id, BookUnitUpdate(**patch), session)

    if action == "generate_outline":
        return outlines_api.generate_outline(
            target_id, outlines_api.OutlineGenerateRequest(), session, llm_call=outline_llm
        )

    if action == "approve_outline":
        return outlines_api.approve_outline(target_id, session)

    if action == "generate_chapter":
        unit = session.get(BookUnit, target_id)
        if not unit:
            raise HTTPException(404, "unit not found")
        return units_api.generate_unit_body(
            unit.outline_id,
            target_id,
            session,
            writer_llm=writer_llm,
            reviewer_llm=reviewer_llm,
            reviser_llm=reviser_llm,
        )

    raise HTTPException(400, f"실행할 수 없는 action: {action}")


def _serialize_result(session: Session, result):
    """_execute_action 결과를 이후 session.commit() 이 일어나도 안전하도록
    즉시 plain dict/값으로 캡처한다.

    주의: SQLAlchemy가 만료(expired) 시킨 객체는 .model_dump()만 호출해서는
    다시 채워지지 않는다(내부적으로 getattr을 안 거치는 경로를 타는 경우가 있음).
    session.refresh()로 명시적으로 먼저 채워야 한다.
    """
    if isinstance(result, dict):
        return {key: _serialize_result(session, value) for key, value in result.items()}
    if hasattr(result, "model_dump"):
        try:
            session.refresh(result)
        except Exception:
            pass
        return result.model_dump()
    return result


@router.post("/api/chat")
def chat(
    payload: ChatRequest,
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
    qa_llm=Depends(get_writer_llm_call),
    writer_llm=Depends(get_writer_llm_call),
    reviewer_llm=Depends(get_reviewer_llm_call),
    reviser_llm=Depends(get_reviser_llm_call),
):
    book = session.get(BookProject, payload.book_id)
    if not book:
        raise HTTPException(404, "book not found")
    config = session.exec(
        select(BookConfig).where(BookConfig.book_id == payload.book_id)
    ).first()

    intent = classify_intent(
        message=payload.message,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        llm_call=llm_call,
    )
    action = intent["action"]

    if action == "ask":
        profiles = session.exec(
            select(SourceProfile)
            .join(SourceDocument, SourceProfile.source_id == SourceDocument.source_id)
            .where(SourceDocument.book_id == payload.book_id)
        ).all()
        context_parts = [p.summary for p in profiles if p.summary]
        if payload.scope_type == "unit" and payload.scope_id:
            unit = session.get(BookUnit, payload.scope_id)
            if unit and unit.body_md:
                context_parts.append(unit.body_md)
        context_text = "\n\n".join(context_parts) or "(참고할 자료가 없습니다)"

        answer = answer_question(message=payload.message, context_text=context_text, llm_call=qa_llm)
        return {"intent": intent, "status": "answered", "answer": answer}

    target_type: str
    target_id: str
    patch: dict = {}
    summary = ""

    if action == "edit_config":
        target_type, target_id = "BookConfig", payload.book_id
        patch = extract_config_patch(message=payload.message, llm_call=llm_call)
        if not patch:
            raise HTTPException(400, "메시지에서 변경할 설정 항목을 찾지 못했습니다.")
        summary = f"책 설정 변경: {patch}"

    elif action == "edit_unit":
        unit_id = _resolve_unit_id(
            session, payload.book_id, payload.message, payload.scope_type, payload.scope_id
        )
        if not unit_id:
            raise HTTPException(400, "어떤 챕터를 수정할지 특정할 수 없습니다. 몇 장인지 명시해주세요.")
        target_type, target_id = "BookUnit", unit_id
        patch = extract_unit_patch(message=payload.message, llm_call=llm_call)
        if not patch:
            raise HTTPException(400, "메시지에서 변경할 챕터 항목을 찾지 못했습니다.")
        summary = f"챕터 변경: {patch}"

    elif action == "generate_outline":
        target_type, target_id = "BookOutline", payload.book_id
        summary = "목차 새로 생성"

    elif action == "approve_outline":
        target_type, target_id = "BookOutline", payload.book_id
        summary = "목차 승인"

    elif action == "generate_chapter":
        unit_id = _resolve_unit_id(
            session, payload.book_id, payload.message, payload.scope_type, payload.scope_id
        )
        if not unit_id:
            raise HTTPException(400, "어떤 챕터를 집필할지 특정할 수 없습니다. 몇 장인지 명시해주세요.")
        target_type, target_id = "BookUnit", unit_id
        summary = "챕터 본문 생성"

    else:
        raise HTTPException(400, f"알 수 없는 action: {action}")

    approval_mode = config.approval_mode if config else "balanced"

    if needs_approval(action, approval_mode):
        action_plan = ActionPlan(
            book_id=payload.book_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            patch=patch,
            summary=summary,
            status="pending",
        )
        session.add(action_plan)
        session.commit()
        session.refresh(action_plan)
        return {"intent": intent, "status": "pending_approval", "action": action_plan}

    raw_result = _execute_action(
        session,
        action,
        target_id,
        patch,
        writer_llm=writer_llm,
        reviewer_llm=reviewer_llm,
        reviser_llm=reviser_llm,
        outline_llm=llm_call,
    )
    result = _serialize_result(session, raw_result)
    return {"intent": intent, "status": "executed", "result": result}


@router.post("/api/actions/{action_id}/approve")
def approve_action(
    action_id: str,
    session: Session = Depends(get_session),
    writer_llm=Depends(get_writer_llm_call),
    reviewer_llm=Depends(get_reviewer_llm_call),
    reviser_llm=Depends(get_reviser_llm_call),
    outline_llm=Depends(get_llm_call),
):
    action_plan = session.get(ActionPlan, action_id)
    if not action_plan:
        raise HTTPException(404, "action not found")
    if action_plan.status != "pending":
        raise HTTPException(400, f"이미 처리된 요청입니다 (status={action_plan.status})")

    try:
        raw_result = _execute_action(
            session,
            action_plan.action,
            action_plan.target_id,
            action_plan.patch,
            writer_llm=writer_llm,
            reviewer_llm=reviewer_llm,
            reviser_llm=reviser_llm,
            outline_llm=outline_llm,
        )
    except HTTPException:
        action_plan.status = "failed"
        session.add(action_plan)
        session.commit()
        raise

    result = _serialize_result(session, raw_result)  # 아래 commit 전에 값을 미리 굳혀둔다
    action_plan.status = "applied"
    session.add(action_plan)
    session.commit()
    session.refresh(action_plan)
    return {"action": action_plan, "result": result}


@router.post("/api/actions/{action_id}/reject")
def reject_action(action_id: str, session: Session = Depends(get_session)):
    action_plan = session.get(ActionPlan, action_id)
    if not action_plan:
        raise HTTPException(404, "action not found")
    if action_plan.status != "pending":
        raise HTTPException(400, f"이미 처리된 요청입니다 (status={action_plan.status})")

    action_plan.status = "rejected"
    session.add(action_plan)
    session.commit()
    session.refresh(action_plan)
    return action_plan
