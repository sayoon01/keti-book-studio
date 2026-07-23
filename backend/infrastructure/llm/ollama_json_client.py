from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx


class OllamaClientError(RuntimeError):
    """Ollama 요청 처리 중 발생한 기본 예외입니다."""


class OllamaError(OllamaClientError):
    """Ollama 호출 또는 응답 처리 실패."""


class OllamaModelNotFoundError(OllamaClientError):
    """요청한 Ollama 모델이 설치되어 있지 않습니다."""


class OllamaIncompleteResponseError(OllamaClientError):
    """Ollama가 생성을 완료하지 못한 채 응답을 종료했습니다."""


class OllamaResponseParseError(OllamaClientError):
    """Ollama 응답을 정상적인 JSON으로 해석할 수 없습니다."""


class OllamaLowQualityResponseError(OllamaClientError):
    """응답이 형식상 파싱되지만 최소 품질 기준을 충족하지 못했습니다."""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_retries: int
    retry_delay_seconds: float

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        return cls(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ).rstrip("/"),
            model=os.getenv(
                "BOOK_STUDIO_MODEL",
                "gemma4-31b-32k:latest",
            ).strip(),
            timeout_seconds=float(
                os.getenv(
                    "OLLAMA_TIMEOUT_SECONDS",
                    "600",
                )
            ),
            temperature=float(
                os.getenv(
                    "BOOK_STUDIO_TEMPERATURE",
                    "0.3",
                )
            ),
            max_retries=int(
                os.getenv(
                    "OLLAMA_MAX_RETRIES",
                    "2",
                )
            ),
            retry_delay_seconds=float(
                os.getenv(
                    "OLLAMA_RETRY_DELAY_SECONDS",
                    "2",
                )
            ),
        )


def _validate_chat_completion(
    payload: dict[str, Any],
) -> str:
    """Ollama /api/chat 응답이 완료됐는지 확인하고 content를 반환합니다."""
    message = payload.get("message")

    if not isinstance(message, dict):
        raise OllamaIncompleteResponseError(
            "Ollama 응답에 message 객체가 없습니다."
        )

    raw_content = message.get("content")

    if not isinstance(raw_content, str):
        raise OllamaIncompleteResponseError(
            "Ollama 응답의 message.content가 문자열이 아닙니다."
        )

    content = raw_content.strip()

    if not content:
        raise OllamaIncompleteResponseError(
            "Ollama가 빈 응답을 반환했습니다."
        )

    done = payload.get("done")
    done_reason = payload.get("done_reason")

    if done is not True:
        raise OllamaIncompleteResponseError(
            "Ollama 생성이 완료되지 않았습니다. "
            f"done={done!r}, "
            f"done_reason={done_reason!r}, "
            f"content_length={len(content)}"
        )

    return content


def _has_degenerate_repetition(
    text: str,
) -> bool:
    normalized = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not normalized:
        return True

    repeated_word_pattern = re.compile(
        r"\b([A-Za-z가-힣]{1,20})"
        r"(?:\s+\1){4,}\b",
        re.IGNORECASE,
    )

    if repeated_word_pattern.search(normalized):
        return True

    repeated_chunk_pattern = re.compile(
        r"(.{1,8})\1{5,}",
        re.DOTALL,
    )

    if repeated_chunk_pattern.search(normalized):
        return True

    words = re.findall(
        r"[A-Za-z가-힣0-9]+",
        normalized.lower(),
    )

    if len(words) >= 20:
        counts = Counter(words)
        most_common_count = counts.most_common(1)[0][1]

        if most_common_count / len(words) >= 0.25:
            return True

    return False


def _parse_json_response(
    raw_content: str,
) -> dict[str, Any]:
    content = raw_content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as original_error:
        repaired = _try_repair_truncated_json(content)

        if repaired is None:
            raise OllamaResponseParseError(
                "Ollama 응답을 JSON으로 해석할 수 없습니다. "
                f"error={original_error}"
            ) from original_error

        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError as repaired_error:
            raise OllamaResponseParseError(
                "JSON 복구 후에도 파싱할 수 없습니다. "
                f"error={repaired_error}"
            ) from repaired_error

    if not isinstance(parsed, dict):
        raise OllamaResponseParseError(
            "Ollama JSON 최상위 값은 객체여야 합니다. "
            f"actual_type={type(parsed).__name__}"
        )

    return parsed


def _try_repair_truncated_json(
    content: str,
) -> str | None:
    """가벼운 JSON 복구만 시도합니다. 잘린 문자열은 닫아줍니다."""
    candidate = content.strip()

    if not candidate.startswith("{"):
        return None

    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        candidate,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if fenced_match:
        candidate = fenced_match.group(1).strip()

    first_brace = candidate.find("{")
    if first_brace < 0:
        return None

    candidate = candidate[first_brace:]

    suffixes = [
        '"}',
        '"\n}',
        '",\n  "writing_notes": []\n}',
        '",\n  "applied_changes": []\n}',
        '"]}',
        '}}',
        '"}]',
        '"}]}\n',
    ]

    for suffix in suffixes:
        try:
            json.loads(candidate + suffix)
        except json.JSONDecodeError:
            continue

        return candidate + suffix

    quote_count = 0
    escaped = False

    for char in candidate:
        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            quote_count += 1

    repaired = candidate

    if quote_count % 2 == 1:
        repaired += '"'

    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")

    repaired += "]" * max(open_brackets, 0)
    repaired += "}" * max(open_braces, 0)

    try:
        json.loads(repaired)
    except json.JSONDecodeError:
        return None

    return repaired


class OllamaJsonClient:
    """
    Ollama /api/chat을 호출하고 JSON 객체를 반환합니다.

    Stage Agent에서는 이 클래스의 generate_json()만 사용하면 됩니다.
    """

    def __init__(
        self,
        settings: OllamaSettings | None = None,
    ) -> None:
        self.settings = settings or OllamaSettings.from_env()
        self._verified_models: set[str] = set()

    async def ensure_model_available(
        self,
        model: str | None = None,
    ) -> None:
        target_model = model or self.settings.model

        if target_model in self._verified_models:
            return

        tags = await self.health_check()

        models = tags.get("models", [])

        available_models: set[str] = set()

        for item in models:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            model_name = item.get("model")

            if isinstance(name, str):
                available_models.add(name)

            if isinstance(model_name, str):
                available_models.add(model_name)

        if target_model not in available_models:
            available_text = ", ".join(
                sorted(available_models)
            )

            raise OllamaModelNotFoundError(
                f"요청한 Ollama 모델이 없습니다: {target_model}\n"
                f"사용 가능한 모델: {available_text}"
            )

        self._verified_models.add(target_model)

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        selected_model = model or self.settings.model

        selected_temperature = (
            self.settings.temperature
            if temperature is None
            else temperature
        )

        await self.ensure_model_available(
            selected_model
        )

        last_error: Exception | None = None
        total_attempts = self.settings.max_retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                response_payload = await self._request_chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=selected_model,
                    temperature=selected_temperature,
                )

                raw_content = _validate_chat_completion(
                    response_payload
                )

                if _has_degenerate_repetition(raw_content):
                    raise OllamaLowQualityResponseError(
                        "Ollama 응답에서 비정상적인 반복 "
                        "패턴이 탐지되었습니다. "
                        f"attempt={attempt}, "
                        f"model={selected_model}, "
                        f"content_length={len(raw_content)}"
                    )

                return _parse_json_response(raw_content)

            except (
                OllamaIncompleteResponseError,
                OllamaResponseParseError,
                OllamaLowQualityResponseError,
                httpx.TimeoutException,
                httpx.RemoteProtocolError,
            ) as exc:
                last_error = exc

                if attempt >= total_attempts:
                    break

                await asyncio.sleep(
                    self.settings.retry_delay_seconds
                    * attempt
                )

        raise OllamaClientError(
            "Ollama JSON 생성에 실패했습니다. "
            f"model={selected_model}, "
            f"attempts={total_attempts}, "
            f"last_error={last_error}"
        ) from last_error

    async def _request_chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
            },
        }

        timeout = httpx.Timeout(
            timeout=self.settings.timeout_seconds,
            connect=30.0,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.settings.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()

        except httpx.ConnectError as exc:
            raise OllamaError(
                "Ollama 서버에 연결할 수 없습니다. "
                f"base_url={self.settings.base_url}"
            ) from exc

        except httpx.TimeoutException:
            raise

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:2000]

            raise OllamaError(
                "Ollama HTTP 오류가 발생했습니다. "
                f"status={exc.response.status_code}, body={body}"
            ) from exc

        try:
            response_data = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseParseError(
                f"Ollama HTTP 응답이 JSON이 아닙니다: "
                f"{response.text[:2000]}"
            ) from exc

        if not isinstance(response_data, dict):
            raise OllamaResponseParseError(
                "Ollama HTTP 응답이 JSON 객체가 아닙니다."
            )

        return response_data

    async def health_check(self) -> dict[str, Any]:
        timeout = httpx.Timeout(
            timeout=30.0,
            connect=10.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.settings.base_url}/api/tags"
            )
            response.raise_for_status()

        return response.json()
