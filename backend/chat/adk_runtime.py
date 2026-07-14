"""ADK Runner + SessionService 관리.

핵심 함수(run_chat_turn_with, get_history_with)는 runner/session_service를
인자로 받는다 — 테스트에서 진짜 Ollama 대신 가짜 모델로 만든 runner를
그대로 주입해서 네트워크 없이 세션 메모리 로직을 검증하기 위함.

실서비스에서 쓰는 run_chat_turn/get_history는 프로세스 전역 싱글톤
(_runner, _session_service)을 감싸는 얇은 래퍼일 뿐이다.
"""

from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService, InMemorySessionService
from google.genai import types

from backend.chat.adk_agent import build_chat_agent

APP_NAME = "keti-book-studio"


async def ensure_session(
    session_service: BaseSessionService,
    app_name: str,
    *,
    user_id: str,
    session_id: str,
    book_id: Optional[str] = None,
) -> None:
    existing = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={"book_id": book_id} if book_id else {},
        )


async def run_chat_turn_with(
    runner: Runner,
    session_service: BaseSessionService,
    app_name: str,
    *,
    user_id: str,
    session_id: str,
    book_id: Optional[str],
    message: str,
) -> str:
    await ensure_session(session_service, app_name, user_id=user_id, session_id=session_id, book_id=book_id)

    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.content and event.content.parts:
            # thought=True 파트는 모델의 내부 추론 과정이라 사용자에게 보여주면 안 된다.
            text_parts = [
                p.text
                for p in event.content.parts
                if getattr(p, "text", None) and getattr(p, "thought", None) is not True
            ]
            if text_parts:
                final_text = "".join(text_parts)
    return final_text


async def get_history_with(
    session_service: BaseSessionService, app_name: str, *, user_id: str, session_id: str
) -> list[dict]:
    session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
    if not session:
        return []

    history = []
    for event in session.events:
        if not event.content or not event.content.parts:
            continue
        text = "".join(
            p.text
            for p in event.content.parts
            if getattr(p, "text", None) and getattr(p, "thought", None) is not True
        )
        if text:
            history.append({"author": event.author, "text": text})
    return history


_session_service = InMemorySessionService()
_agent = build_chat_agent()
_runner = Runner(agent=_agent, app_name=APP_NAME, session_service=_session_service)


async def run_chat_turn(*, user_id: str, session_id: str, book_id: Optional[str], message: str) -> str:
    return await run_chat_turn_with(
        _runner, _session_service, APP_NAME,
        user_id=user_id, session_id=session_id, book_id=book_id, message=message,
    )


async def get_history(*, user_id: str, session_id: str) -> list[dict]:
    return await get_history_with(_session_service, APP_NAME, user_id=user_id, session_id=session_id)
