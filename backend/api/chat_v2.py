from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.chat.adk_runtime import get_history, run_chat_turn

router = APIRouter(tags=["chat-v2"])


class ChatV2Request(BaseModel):
    book_id: Optional[str] = None
    user_id: str = "default-user"
    session_id: str
    message: str


@router.post("/api/chat/v2")
async def chat_v2(payload: ChatV2Request):
    """Phase 10b: ADK SessionService 기반 실제 대화 메모리가 있는 채팅.

    기존 /api/chat(Phase 7, stateless)과 병행 운영한다.
    아직 도구(function calling)는 없어서 설정/목차/챕터를 직접 바꾸지는
    못하고 대화만 가능하다 — Phase 10c에서 도구가 추가된다.
    """
    answer = await run_chat_turn(
        user_id=payload.user_id,
        session_id=payload.session_id,
        book_id=payload.book_id,
        message=payload.message,
    )
    return {"answer": answer, "session_id": payload.session_id}


@router.get("/api/chat/v2/history")
async def chat_v2_history(user_id: str, session_id: str):
    history = await get_history(user_id=user_id, session_id=session_id)
    return {"history": history}
