from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import BookConfig, BookConfigUpdate

router = APIRouter(prefix="/api/books/{book_id}/config", tags=["config"])


def _get_config_or_404(session: Session, book_id: str) -> BookConfig:
    config = session.exec(select(BookConfig).where(BookConfig.book_id == book_id)).first()
    if not config:
        raise HTTPException(404, "config not found for this book")
    return config


@router.get("", response_model=BookConfig)
def get_config(book_id: str, session: Session = Depends(get_session)):
    return _get_config_or_404(session, book_id)


@router.patch("", response_model=BookConfig)
def update_config(book_id: str, payload: BookConfigUpdate, session: Session = Depends(get_session)):
    config = _get_config_or_404(session, book_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    config.version += 1

    session.add(config)
    session.commit()
    session.refresh(config)
    return config
