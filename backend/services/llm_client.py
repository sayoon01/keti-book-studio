"""Ollama 호출 클라이언트.

기존 keti-workOS에서 쓰던 것과 동일하게 로컬 Ollama + 모델 조합을 그대로 사용한다.
Research Agent(및 이후 Writer/Reviewer)는 이 함수를 직접 import하지 않고
FastAPI Depends로 주입받는다 -> 테스트에서 가짜 LLM으로 손쉽게 교체 가능.
"""

import os

import httpx

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:27b")


def call_ollama(system_prompt: str, user_prompt: str, *, model: str | None = None, timeout: float = 180.0) -> str:
    """Ollama /api/chat 호출, 모델의 텍스트 응답(문자열)을 그대로 반환한다.

    format="json" 옵션으로 모델이 JSON만 반환하도록 강제한다.
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def get_llm_call():
    """FastAPI Depends로 주입되는 지점. 테스트에서 app.dependency_overrides로 교체한다."""
    return call_ollama
