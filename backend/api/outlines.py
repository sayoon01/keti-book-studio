from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import BookOutline, BookUnit, BookUnitRead

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


@router.post("/approve")
def approve_outline(book_id: str, session: Session = Depends(get_session)):
    """목차 승인. 승인 전에는 어떤 경로(폼/채팅)로도 unit.generate 호출이
    막혀 있어야 한다 (Phase 4의 units.generate 엔드포인트에서 이 status를 확인)."""
    outline = _get_outline_or_404(session, book_id)

    units = session.exec(
        select(BookUnit).where(BookUnit.outline_id == outline.outline_id)
    ).all()
    if not units:
        raise HTTPException(400, "목차에 챕터가 하나도 없습니다. 승인할 수 없습니다.")

    outline.status = "approved"
    session.add(outline)
    session.commit()
    session.refresh(outline)
    return outline