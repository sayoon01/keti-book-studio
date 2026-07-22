from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Ollama 호출 또는 응답 처리 실패."""


class OllamaResponseParseError(OllamaError):
    """Ollama 응답을 JSON으로 변환하지 못한 경우."""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float

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
            ),
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
        )


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

            raise OllamaError(
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
        request_model = model or self.settings.model

        await self.ensure_model_available(
            request_model
        )

        request_temperature = (
            self.settings.temperature
            if temperature is None
            else temperature
        )

        payload = {
            "model": request_model,
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
                "temperature": request_temperature,
                "num_predict": 8192,
            },
        }

        timeout = httpx.Timeout(
            timeout=self.settings.timeout_seconds,
            connect=30.0,
        )

        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                return await self._request_json_object(
                    payload=payload,
                    timeout=timeout,
                )
            except OllamaResponseParseError as exc:
                last_error = exc

                if attempt >= 3:
                    break

        assert last_error is not None
        raise last_error

    async def _request_json_object(
        self,
        *,
        payload: dict[str, Any],
        timeout: httpx.Timeout,
    ) -> dict[str, Any]:
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

        except httpx.TimeoutException as exc:
            raise OllamaError(
                "Ollama 응답 시간이 초과되었습니다. "
                f"timeout={self.settings.timeout_seconds}"
            ) from exc

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

        message = response_data.get("message")

        if not isinstance(message, dict):
            raise OllamaResponseParseError(
                "Ollama 응답에 message 객체가 없습니다."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseParseError(
                "Ollama 응답의 message.content가 비어 있습니다."
            )

        return self._parse_json_object(content)

    @classmethod
    def _parse_json_object(
        cls,
        raw_content: str,
    ) -> dict[str, Any]:
        content = raw_content.strip()

        # 1. 정상 JSON 응답
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            return parsed

        # 2. ```json ... ``` 코드블록 제거
        fenced_match = re.search(
            r"```(?:json)?\s*(\{.*\})\s*```",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if fenced_match:
            fenced_content = fenced_match.group(1)

            try:
                parsed = json.loads(fenced_content)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, dict):
                return parsed

        # 3. 첫 번째 { 부터 마지막 }까지 추출
        first_brace = content.find("{")
        last_brace = content.rfind("}")

        if (
            first_brace >= 0
            and last_brace > first_brace
        ):
            candidate = content[first_brace:last_brace + 1]

            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, dict):
                return parsed

        # 4. 잘린 JSON 복구 시도
        if first_brace >= 0:
            repaired = cls._try_repair_truncated_json(
                content[first_brace:]
            )

            if repaired is not None:
                return repaired

        raise OllamaResponseParseError(
            "Ollama 응답에서 JSON 객체를 추출할 수 없습니다.\n"
            f"raw_content={content[:3000]}"
        )

    @classmethod
    def _try_repair_truncated_json(
        cls,
        content: str,
    ) -> dict[str, Any] | None:
        candidate = content.rstrip()

        if not candidate.startswith("{"):
            return None

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
                parsed = json.loads(candidate + suffix)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, dict):
                return parsed

        # 열린 따옴표/괄호를 닫는 단순 복구
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
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            return None

        if isinstance(parsed, dict):
            return parsed

        return None

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
