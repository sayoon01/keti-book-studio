from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import (
    BookOutline,
    BookUnit,
    BookUnitCreate,
    BookUnitRead,
    BookUnitUpdate,
    ReorderRequest,
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
    """폼(목차 편집기)과 채팅이 동일하게 호출하는 엔드포인트.

    target_characters 가 바뀌면 config.total_target_characters 가 자동 재계산된다.
    """
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