from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import AgentTrace

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("", response_model=list[AgentTrace])
def list_traces(
    session_id: Optional[str] = None,
    book_id: Optional[str] = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    query = select(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(limit)
    if session_id:
        query = query.where(AgentTrace.session_id == session_id)
    if book_id:
        query = query.where(AgentTrace.book_id == book_id)
    return session.exec(query).all()
