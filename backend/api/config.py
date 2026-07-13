from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.agents.config_designer import suggest_book_config
from backend.services.llm_client import get_llm_call
from backend.storage.database import get_session
from backend.storage.models import BookConfig, BookConfigUpdate, BookProject, Persona, SourceDocument, SourceProfile

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


class ConfigSuggestRequest(BaseModel):
    purpose: Optional[str] = None
    source_ids: Optional[list[str]] = None


@router.post("/suggest")
def suggest_config(
    book_id: str,
    payload: ConfigSuggestRequest = ConfigSuggestRequest(),
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    config = _get_config_or_404(session, book_id)
    book = session.get(BookProject, book_id)

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

    personas = session.exec(select(Persona)).all()
    persona_options = [
        {
            "persona_id": p.persona_id,
            "name": p.name,
            "description": (p.defaults or {}).get("description", ""),
        }
        for p in personas
    ]
    if not persona_options:
        raise HTTPException(500, "등록된 Persona가 없습니다. 서버 시작 시 시딩이 되었는지 확인해주세요.")

    result = suggest_book_config(
        profiles=[p.model_dump() for p in profiles],
        purpose=payload.purpose,
        persona_options=persona_options,
        llm_call=llm_call,
    )

    for field, value in result["config_patch"].items():
        setattr(config, field, value)
    config.version += 1
    session.add(config)

    if result["recommended_persona_id"] and not book.persona_id:
        book.persona_id = result["recommended_persona_id"]
        session.add(book)

    session.commit()
    session.refresh(config)

    return {
        "config": config,
        "suggested_chapter_count": result["suggested_chapter_count"],
        "recommended_persona_id": result["recommended_persona_id"],
        "recommendation_reason": result["recommendation_reason"],
        "alternative_persona_ids": result["alternative_persona_ids"],
        "book_persona_id": book.persona_id,
    }
