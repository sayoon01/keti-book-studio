from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.validators import (
    ArtifactValidationError,
)
from backend.infrastructure.llm import (
    OllamaClient,
    OllamaClientError,
)


logger = logging.getLogger(__name__)


class StructuredGenerationError(RuntimeError):
    """
    구조화 JSON 역할의 Generation 처리 실패.
    """


PayloadEnricher = Callable[
    [dict[str, Any], Any, int],
    dict[str, Any],
]

ArtifactValidator = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


class StructuredJsonHandler:
    """
    JSON 응답을 생성하는 역할의 공통 실행기.

    적용 대상:
    - Researcher
    - Reviewer
    - Technical Reviewer
    - Editor
    - Reader

    책임:
    - ModelRouter 설정 조회
    - OllamaClient.generate_json 호출
    - metadata 추가
    - Validator 실행
    - 제한적 재시도

    역할별 Handler가 담당할 부분:
    - Prompt 생성
    - chapter_id/title 등 결과 보정
    - 역할별 Validator 선택
    """

    def __init__(
        self,
        *,
        role: GenerationRole,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError(
                "max_attempts는 0보다 커야 합니다."
            )

        self._role = role
        self._client = client
        self._model_router = model_router
        self._max_attempts = max_attempts

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        validator: ArtifactValidator,
        enrich_payload: PayloadEnricher,
        operation_name: str,
    ) -> dict[str, Any]:
        config = self._model_router.get_config(
            self._role
        )

        if not config.enabled:
            raise StructuredGenerationError(
                f"{self._role.value} 역할이 비활성화되어 있습니다."
            )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self._max_attempts + 1,
        ):
            logger.info(
                "%s started: attempt=%s/%s model=%s "
                "num_predict=%s num_ctx=%s",
                operation_name,
                attempt,
                self._max_attempts,
                config.model,
                config.num_predict,
                config.num_ctx,
            )

            try:
                result = await self._client.generate_json(
                    model=config.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=config.temperature,
                    num_predict=config.num_predict,
                    num_ctx=config.num_ctx,
                    timeout_seconds=config.timeout_seconds,
                )

                payload = dict(result.data)

                payload = enrich_payload(
                    payload,
                    result.metadata,
                    attempt,
                )

                validated = validator(payload)

                logger.info(
                    "%s completed: model=%s attempt=%s",
                    operation_name,
                    config.model,
                    attempt,
                )

                return validated

            except (
                OllamaClientError,
                ArtifactValidationError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                last_error = exc

                logger.warning(
                    "%s failed: attempt=%s/%s "
                    "model=%s error=%s",
                    operation_name,
                    attempt,
                    self._max_attempts,
                    config.model,
                    exc,
                )

                if attempt < self._max_attempts:
                    await asyncio.sleep(1)

        raise StructuredGenerationError(
            f"{operation_name} 처리에 실패했습니다. "
            f"role={self._role.value}, "
            f"model={config.model}, "
            f"attempts={self._max_attempts}, "
            f"last_error={last_error}"
        ) from last_error


def metadata_to_dict(
    metadata: Any,
) -> dict[str, Any]:
    """
    Ollama 응답 metadata를 직렬화 가능한 dictionary로 변환한다.
    """

    return {
        "model": getattr(metadata, "model", ""),
        "attempts": getattr(metadata, "attempts", 1),
        "latency_seconds": getattr(
            metadata,
            "latency_seconds",
            0.0,
        ),
        "done_reason": getattr(
            metadata,
            "done_reason",
            None,
        ),
        "prompt_eval_count": getattr(
            metadata,
            "prompt_eval_count",
            None,
        ),
        "eval_count": getattr(
            metadata,
            "eval_count",
            None,
        ),
    }
