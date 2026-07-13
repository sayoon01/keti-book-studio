from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.agents.reviewer import review_chapter
from backend.agents.reviser import revise_chapter
from backend.agents.writer import write_chapter
from backend.services.llm_client import get_reviewer_llm_call, get_reviser_llm_call, get_writer_llm_call
from backend.services.persona_store import read_persona_files
from backend.storage.database import get_session
from backend.storage.models import (
    BookConfig,
    BookOutline,
    BookProject,
    BookUnit,
    BookUnitCreate,
    BookUnitRead,
    BookUnitUpdate,
    Persona,
    ReorderRequest,
    SourceDocument,
)
from backend.storage.recalculation import assert_outline_editable, recalc_config_from_outline

router = APIRouter(prefix="/api/outlines/{outline_id}/units", tags=["units"])


def _get_outline_or_404(session: Session, outline_id: str) -> BookOutline:
    outline = session.get(BookOutline, outline_id)
    if not outline:
        raise HTTPException(404, "outline not found")
    return outline


def _get_unit_or_404(session: Session, unit_id: str) -> BookUnit:
    unit = session.get(BookUnit, unit_id)
    if not unit:
        raise HTTPException(404, "unit not found")
    return unit


@router.post("", response_model=BookUnitRead)
def create_unit(outline_id: str, payload: BookUnitCreate, session: Session = Depends(get_session)):
    outline = _get_outline_or_404(session, outline_id)
    assert_outline_editable(outline)

    if payload.order is None:
        max_order = session.exec(
            select(BookUnit.order)
            .where(BookUnit.outline_id == outline_id)
            .order_by(BookUnit.order.desc())
        ).first()
        order = (max_order or 0) + 1
    else:
        order = payload.order

    unit = BookUnit(
        outline_id=outline_id,
        order=order,
        **payload.model_dump(exclude={"order"}),
    )
    session.add(unit)
    session.add(outline)
    session.commit()
    session.refresh(unit)

    recalc_config_from_outline(session, outline.book_id)
    return unit


@router.patch("/{unit_id}", response_model=BookUnitRead)
def update_unit(
    outline_id: str, unit_id: str, payload: BookUnitUpdate, session: Session = Depends(get_session)
):
    outline = _get_outline_or_404(session, outline_id)
    unit = _get_unit_or_404(session, unit_id)
    if unit.outline_id != outline_id:
        raise HTTPException(400, "unit does not belong to this outline")

    assert_outline_editable(outline)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)

    session.add(unit)
    session.add(outline)
    session.commit()
    session.refresh(unit)

    recalc_config_from_outline(session, outline.book_id)
    return unit


@router.delete("/{unit_id}", status_code=204)
def delete_unit(outline_id: str, unit_id: str, session: Session = Depends(get_session)):
    outline = _get_outline_or_404(session, outline_id)
    unit = _get_unit_or_404(session, unit_id)
    if unit.outline_id != outline_id:
        raise HTTPException(400, "unit does not belong to this outline")

    assert_outline_editable(outline)

    session.delete(unit)
    session.add(outline)
    session.commit()

    recalc_config_from_outline(session, outline.book_id)


@router.post("/reorder")
def reorder_units(outline_id: str, payload: ReorderRequest, session: Session = Depends(get_session)):
    outline = _get_outline_or_404(session, outline_id)
    assert_outline_editable(outline)

    units = {
        u.unit_id: u
        for u in session.exec(select(BookUnit).where(BookUnit.outline_id == outline_id)).all()
    }
    missing = set(payload.ordered_unit_ids) - set(units.keys())
    if missing:
        raise HTTPException(400, f"unknown unit_ids: {missing}")

    for idx, unit_id in enumerate(payload.ordered_unit_ids):
        units[unit_id].order = idx
        session.add(units[unit_id])

    session.add(outline)
    session.commit()
    return {"ok": True}


def _collect_evidence_chunks(session: Session, book_id: str, unit: BookUnit) -> list[str]:
    query = select(SourceDocument).where(
        SourceDocument.book_id == book_id, SourceDocument.status == "analyzed"
    )
    if unit.source_ids:
        query = query.where(SourceDocument.source_id.in_(unit.source_ids))
    sources = session.exec(query).all()
    return [s.raw_text[:6000] for s in sources if s.raw_text]


@router.post("/{unit_id}/generate")
def generate_unit_body(
    outline_id: str,
    unit_id: str,
    session: Session = Depends(get_session),
    writer_llm=Depends(get_writer_llm_call),
    reviewer_llm=Depends(get_reviewer_llm_call),
    reviser_llm=Depends(get_reviser_llm_call),
):
    """챕터 본문 생성: Writer -> Reviewer -> (필요시) Reviser."""
    outline = _get_outline_or_404(session, outline_id)
    unit = _get_unit_or_404(session, unit_id)
    if unit.outline_id != outline_id:
        raise HTTPException(400, "unit does not belong to this outline")

    if outline.status != "approved":
        raise HTTPException(403, "목차가 아직 승인되지 않았습니다. 먼저 목차를 승인해주세요.")

    book = session.get(BookProject, outline.book_id)
    config = session.exec(
        select(BookConfig).where(BookConfig.book_id == outline.book_id)
    ).first()

    persona_id = unit.persona_id or book.persona_id
    persona = session.get(Persona, persona_id) if persona_id else None
    persona_files = read_persona_files(persona.files) if persona else {}
    writer_md = persona_files.get("writer.md", "")
    reviewer_md = persona_files.get("reviewer.md", "")

    evidence_chunks = _collect_evidence_chunks(session, outline.book_id, unit)
    if not evidence_chunks:
        raise HTTPException(400, "이 챕터에 사용할 분석된 자료가 없습니다.")

    unit.status = "generating"
    session.add(unit)
    session.commit()

    try:
        body_md = write_chapter(
            unit=unit.model_dump(),
            book_config=config.model_dump(),
            persona_writer_md=writer_md,
            evidence_chunks=evidence_chunks,
            llm_call=writer_llm,
        )

        review_result = review_chapter(
            body_md=body_md,
            unit=unit.model_dump(),
            persona_reviewer_md=reviewer_md,
            evidence_chunks=evidence_chunks,
            llm_call=reviewer_llm,
        )

        final_body = body_md
        revised = False
        if review_result["needs_revision"] and review_result["issues"]:
            final_body = revise_chapter(
                body_md=body_md,
                issues=review_result["issues"],
                unit=unit.model_dump(),
                persona_writer_md=writer_md,
                llm_call=reviser_llm,
            )
            revised = True

    except HTTPException:
        raise
    except Exception as exc:
        unit.status = "approved"
        session.add(unit)
        session.commit()
        raise HTTPException(502, f"본문 생성에 실패했습니다: {exc}") from exc

    unit.body_md = final_body
    unit.body_version += 1
    unit.status = "reviewed" if revised else "generated"
    session.add(unit)
    session.commit()
    session.refresh(unit)

    return {
        "unit": BookUnitRead.model_validate(unit),
        "review": review_result,
        "revised": revised,
    }
