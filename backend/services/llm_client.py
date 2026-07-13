"""Ollama 호출 클라이언트.

Writer/Reviewer/Reviser는 서로 다른 모델을 쓸 수 있게 각각 별도의
Depends 주입 함수를 제공한다 (같은 모델이 쓰고 검토하면 같은 맹점을
못 잡아내는 문제 때문 — Reviewer만 계열이 다른 모델을 쓴다).
"""

import os

import httpx

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:27b")

WRITER_MODEL = os.environ.get("OLLAMA_WRITER_MODEL", OLLAMA_MODEL)
REVIEWER_MODEL = os.environ.get("OLLAMA_REVIEWER_MODEL", "qwen3:32b")
REVISER_MODEL = os.environ.get("OLLAMA_REVISER_MODEL", WRITER_MODEL)


def call_ollama(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: float = 600.0,
    json_mode: bool = True,
) -> str:
    """Ollama /api/chat 호출, 모델의 텍스트 응답(문자열)을 그대로 반환한다.

    json_mode=True 면 format="json" 을 강제한다 (구조화된 데이터를 뽑는 Agent용).
    본문 집필처럼 순수 마크다운 텍스트가 필요한 경우 json_mode=False 로 호출한다.
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def get_llm_call():
    """구조화(JSON) 응답이 필요한 Agent(Research/Config/Outline)용. 기본 모델 사용."""
    return call_ollama


def get_writer_llm_call():
    """Writer: 순수 마크다운 텍스트, 기본(Writer) 모델."""

    def _call(system_prompt: str, user_prompt: str) -> str:
        return call_ollama(system_prompt, user_prompt, model=WRITER_MODEL, json_mode=False)

    return _call


def get_reviewer_llm_call():
    """Reviewer: JSON 구조화 검토 결과, Writer와 다른 계열 모델."""

    def _call(system_prompt: str, user_prompt: str) -> str:
        return call_ollama(system_prompt, user_prompt, model=REVIEWER_MODEL, json_mode=True)

    return _call


def get_reviser_llm_call():
    """Reviser: 순수 마크다운 텍스트, Writer와 같은 모델(문체 유지 목적)."""

    def _call(system_prompt: str, user_prompt: str) -> str:
        return call_ollama(system_prompt, user_prompt, model=REVISER_MODEL, json_mode=False)

    return _call
