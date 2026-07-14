from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.skills.outline_planner import suggest_outline
from backend.services.llm_client import get_llm_call
from backend.services.persona_store import read_persona_files
from backend.storage.database import get_session
from backend.storage.models import (
    BookConfig,
    BookOutline,
    BookProject,
    BookUnit,
    BookUnitRead,
    Persona,
    SourceDocument,
    SourceProfile,
)
from backend.storage.recalculation import recalc_config_from_outline
from backend.storage.versioning import log_version

router = APIRouter(prefix="/api/books/{book_id}/outline", tags=["outline"])


def _get_outline_or_404(session: Session, book_id: str) -> BookOutline:
    outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()
    if not outline:
        raise HTTPException(404, "outline not found for this book")
    return outline


@router.get("")
def get_outline(book_id: str, session: Session = Depends(get_session)):
    outline = _get_outline_or_404(session, book_id)
    units = session.exec(
        select(BookUnit)
        .where(BookUnit.outline_id == outline.outline_id)
        .order_by(BookUnit.order)
    ).all()
    return {"outline": outline, "units": [BookUnitRead.model_validate(u) for u in units]}


class OutlineGenerateRequest(BaseModel):
    source_ids: Optional[list[str]] = None
    chapter_count: Optional[int] = None


@router.post("/generate")
def generate_outline(
    book_id: str,
    payload: OutlineGenerateRequest = OutlineGenerateRequest(),
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    """AI가 목차 초안을 생성한다. 재생성은 개별 unit 복원 대상이 아니라
    감사 로그로만 남는다 (전체를 새로 만드는 작업이라 복원이 부담스러움)."""
    outline = _get_outline_or_404(session, book_id)
    book = session.get(BookProject, book_id)
    config = session.exec(select(BookConfig).where(BookConfig.book_id == book_id)).first()

    if not book.persona_id:
        raise HTTPException(400, "먼저 Persona를 선택해주세요 (config/suggest 또는 직접 선택).")

    query = (
        select(SourceProfile)
        .join(SourceDocument, SourceProfile.source_id == SourceDocument.source_id)
        .where(SourceDocument.book_id == book_id)
    )
    if payload.source_ids:
        query = query.where(SourceProfile.source_id.in_(payload.source_ids))
    profiles = session.exec(query).all()
    if not profiles:
        raise HTTPException(400, "분석된 자료가 없습니다. 먼저 자료를 업로드하고 분석해주세요.")

    persona = session.get(Persona, book.persona_id)
    planner_md = read_persona_files(persona.files).get("planner.md", "") if persona else ""

    chapter_count_hint = payload.chapter_count or 8

    chapters = suggest_outline(
        profiles=[p.model_dump() for p in profiles],
        config=config.model_dump(),
        persona_planner_md=planner_md,
        chapter_count_hint=chapter_count_hint,
        llm_call=llm_call,
    )
    if not chapters:
        raise HTTPException(502, "AI가 목차를 생성하지 못했습니다. 다시 시도해주세요.")

    existing_units = session.exec(
        select(BookUnit).where(BookUnit.outline_id == outline.outline_id)
    ).all()
    before_count = len(existing_units)
    for u in existing_units:
        session.delete(u)
    session.commit()

    for i, ch in enumerate(chapters, start=1):
        unit = BookUnit(
            outline_id=outline.outline_id,
            order=i,
            title=ch["title"],
            description=ch["description"],
            target_characters=ch["target_characters"],
            must_cover=ch["must_cover"],
        )
        session.add(unit)

    outline.status = "draft"
    session.add(outline)
    session.commit()

    recalc_config_from_outline(session, book_id)

    log_version(
        session, book_id, "outline", outline.outline_id,
        {"before_chapter_count": before_count, "after_chapter_count": len(chapters)},
        label="목차 새로 생성 (복원 미지원)",
    )

    units = session.exec(
        select(BookUnit)
        .where(BookUnit.outline_id == outline.outline_id)
        .order_by(BookUnit.order)
    ).all()
    session.refresh(outline)
    return {"outline": outline, "units": [BookUnitRead.model_validate(u) for u in units]}


@router.post("/approve")
def approve_outline(book_id: str, session: Session = Depends(get_session)):
    outline = _get_outline_or_404(session, book_id)

    units = session.exec(
        select(BookUnit).where(BookUnit.outline_id == outline.outline_id)
    ).all()
    if not units:
        raise HTTPException(400, "목차에 챕터가 하나도 없습니다. 승인할 수 없습니다.")

    before_status = outline.status
    outline.status = "approved"
    session.add(outline)
    session.commit()
    session.refresh(outline)

    log_version(
        session, book_id, "outline", outline.outline_id,
        {"before": {"status": before_status}, "after": {"status": "approved"}},
        label="목차 승인 (복원 미지원)",
    )
    session.refresh(outline)
    return outline
