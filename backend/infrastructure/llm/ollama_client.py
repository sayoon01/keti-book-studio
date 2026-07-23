from __future__ import annotations

import asyncio
from typing import Any

import httpx

from backend.infrastructure.llm.exceptions import (
    OllamaClientError,
    OllamaIncompleteResponseError,
    OllamaModelNotFoundError,
)
from backend.infrastructure.llm.models import (
    OllamaGenerationMetadata,
    OllamaJsonResult,
    OllamaSettings,
    OllamaTextResult,
)
from backend.infrastructure.llm.response_parser import (
    clean_markdown,
    parse_json_object,
    validate_text_quality,
)


class OllamaClient:
    def __init__(
        self,
        settings: OllamaSettings | None = None,
    ) -> None:
        self.settings = settings or OllamaSettings.from_env()
        self._verified_models: set[str] = set()

    async def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        num_predict: int,
        num_ctx: int,
        timeout_seconds: float | None = None,
        minimum_length: int = 300,
    ) -> OllamaTextResult:
        payload = await self._generate_with_retry(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            num_predict=num_predict,
            num_ctx=num_ctx,
            timeout_seconds=timeout_seconds,
            json_mode=False,
        )

        text = clean_markdown(
            self._extract_response(payload)
        )

        validate_text_quality(
            text,
            minimum_length=minimum_length,
        )

        return OllamaTextResult(
            text=text,
            metadata=self._build_metadata(
                payload=payload,
                model=model,
            ),
        )

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        num_predict: int,
        num_ctx: int,
        timeout_seconds: float | None = None,
    ) -> OllamaJsonResult:
        payload = await self._generate_with_retry(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            num_predict=num_predict,
            num_ctx=num_ctx,
            timeout_seconds=timeout_seconds,
            json_mode=True,
        )

        data = parse_json_object(
            self._extract_response(payload)
        )

        return OllamaJsonResult(
            data=data,
            metadata=self._build_metadata(
                payload=payload,
                model=model,
            ),
        )

    async def _generate_with_retry(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        num_predict: int,
        num_ctx: int,
        timeout_seconds: float | None,
        json_mode: bool,
    ) -> dict[str, Any]:
        await self._ensure_model_available(model)

        total_attempts = self.settings.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, total_attempts + 1):
            try:
                payload = await self._request(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    num_predict=num_predict,
                    num_ctx=num_ctx,
                    timeout_seconds=timeout_seconds,
                    json_mode=json_mode,
                )

                payload["_attempts"] = attempt
                return payload

            except (
                httpx.HTTPError,
                OllamaIncompleteResponseError,
            ) as exc:
                last_error = exc

                if attempt >= total_attempts:
                    break

                await asyncio.sleep(
                    self.settings.retry_delay_seconds
                )

        raise OllamaClientError(
            "Ollama 생성에 실패했습니다. "
            f"model={model}, "
            f"attempts={total_attempts}, "
            f"last_error={last_error}"
        ) from last_error

    async def _request(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        num_predict: int,
        num_ctx: int,
        timeout_seconds: float | None,
        json_mode: bool,
    ) -> dict[str, Any]:
        request_payload: dict[str, Any] = {
            "model": model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": self.settings.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
            },
        }

        if json_mode:
            request_payload["format"] = "json"

        timeout = timeout_seconds or self.settings.timeout_seconds

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:
            response = await client.post(
                f"{self.settings.base_url}/api/generate",
                json=request_payload,
            )

            response.raise_for_status()
            payload = response.json()

        if payload.get("done") is not True:
            raise OllamaIncompleteResponseError(
                "Ollama 생성이 완료되지 않았습니다. "
                f"done={payload.get('done')}, "
                f"done_reason={payload.get('done_reason')}, "
                f"response_length="
                f"{len(payload.get('response', ''))}"
            )

        return payload

    async def _ensure_model_available(
        self,
        model: str,
    ) -> None:
        if model in self._verified_models:
            return

        async with httpx.AsyncClient(
            timeout=30
        ) as client:
            response = await client.get(
                f"{self.settings.base_url}/api/tags"
            )
            response.raise_for_status()
            payload = response.json()

        names = {
            item.get("name")
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }

        if model not in names:
            raise OllamaModelNotFoundError(
                f"설치되지 않은 모델입니다: {model}"
            )

        self._verified_models.add(model)

    @staticmethod
    def _extract_response(
        payload: dict[str, Any],
    ) -> str:
        text = payload.get("response")

        if not isinstance(text, str) or not text.strip():
            raise OllamaIncompleteResponseError(
                "Ollama 응답 본문이 비어 있습니다."
            )

        return text.strip()

    @staticmethod
    def _build_metadata(
        *,
        payload: dict[str, Any],
        model: str,
    ) -> OllamaGenerationMetadata:
        total_duration = payload.get("total_duration")

        latency_seconds = (
            total_duration / 1_000_000_000
            if isinstance(total_duration, int)
            else 0.0
        )

        return OllamaGenerationMetadata(
            model=model,
            attempts=int(
                payload.get("_attempts", 1)
            ),
            latency_seconds=round(
                latency_seconds,
                3,
            ),
            done_reason=payload.get("done_reason"),
            prompt_eval_count=payload.get(
                "prompt_eval_count"
            ),
            eval_count=payload.get("eval_count"),
        )
