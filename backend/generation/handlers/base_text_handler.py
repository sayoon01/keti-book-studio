from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

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


class TextGenerationError(RuntimeError):
    """
    Markdown 또는 일반 텍스트 Artifact 생성 실패.
    """


class TextPromptBundleProtocol(Protocol):
    """
    Text Handler가 요구하는 PromptBundle 최소 인터페이스.
    """

    system_prompt: str
    user_prompt: str


ArtifactType = TypeVar(
    "ArtifactType",
    bound=dict[str, Any],
)


@dataclass(frozen=True, slots=True)
class TextExecutionContext:
    """
    텍스트 생성 결과를 Artifact로 조립할 때 사용하는 실행 정보.
    """

    role: GenerationRole
    model: str
    response_format: str
    attempt: int
    metadata: Any


class BaseTextHandler(
    ABC,
    Generic[ArtifactType],
):
    """
    Markdown 또는 일반 텍스트를 생성하는 역할의 공통 Handler.

    Base가 담당하는 것:
    - ModelRouter 조회
    - 역할 활성화 확인
    - Ollama generate_text 호출
    - 재시도
    - 응답 텍스트 추출
    - 공통 오류 처리
    - 공통 로그

    하위 클래스가 담당하는 것:
    - Prompt 생성
    - 입력 검증
    - 텍스트 정리
    - Artifact payload 조립
    - Artifact Validator 호출
    """

    role: GenerationRole
    operation_name: str

    def __init__(
        self,
        *,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError(
                "max_attempts는 0보다 커야 합니다. "
                f"actual={max_attempts}"
            )

        self._client = client
        self._model_router = model_router
        self._max_attempts = max_attempts

        self._validate_class_configuration()

    async def _execute(
        self,
        **inputs: Any,
    ) -> ArtifactType:
        """
        텍스트 생성 공통 실행 흐름.

        1. 입력 검증
        2. Prompt 생성
        3. ModelRouter 설정 조회
        4. Ollama generate_text()
        5. 결과 텍스트 추출
        6. 텍스트 후처리
        7. Artifact 조립 및 검증
        """

        self._validate_inputs(**inputs)

        prompts = self._build_prompts(**inputs)

        system_prompt = str(
            prompts.system_prompt
        ).strip()

        user_prompt = str(
            prompts.user_prompt
        ).strip()

        if not system_prompt:
            raise TextGenerationError(
                f"{self.operation_name} system_prompt가 "
                "비어 있습니다."
            )

        if not user_prompt:
            raise TextGenerationError(
                f"{self.operation_name} user_prompt가 "
                "비어 있습니다."
            )

        config = self._model_router.get_config(
            self.role
        )

        if not config.enabled:
            raise TextGenerationError(
                f"{self.role.value} 역할이 "
                "비활성화되어 있습니다."
            )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self._max_attempts + 1,
        ):
            logger.info(
                "%s started: attempt=%s/%s "
                "model=%s num_predict=%s num_ctx=%s",
                self.operation_name,
                attempt,
                self._max_attempts,
                config.model,
                config.num_predict,
                config.num_ctx,
            )

            try:
                generation_result = (
                    await self._client.generate_text(
                        model=config.model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=config.temperature,
                        num_predict=config.num_predict,
                        num_ctx=config.num_ctx,
                        timeout_seconds=(
                            config.timeout_seconds
                        ),
                        minimum_length=300,
                    )
                )

                raw_text = _extract_generated_text(
                    generation_result
                )

                cleaned_text = self._clean_generated_text(
                    raw_text
                )

                if not cleaned_text:
                    raise ValueError(
                        "모델이 빈 텍스트를 반환했습니다."
                    )

                execution_context = TextExecutionContext(
                    role=self.role,
                    model=config.model,
                    response_format=(
                        config.response_format
                    ),
                    attempt=attempt,
                    metadata=getattr(
                        generation_result,
                        "metadata",
                        None,
                    ),
                )

                artifact = self._build_artifact(
                    generated_text=cleaned_text,
                    execution_context=(
                        execution_context
                    ),
                    **inputs,
                )

                if not isinstance(artifact, dict):
                    raise TypeError(
                        "_build_artifact()는 dictionary를 "
                        "반환해야 합니다."
                    )

                self._log_completion(
                    artifact=artifact,
                    execution_context=(
                        execution_context
                    ),
                )

                return artifact

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
                    self.operation_name,
                    attempt,
                    self._max_attempts,
                    config.model,
                    exc,
                )

                if attempt < self._max_attempts:
                    await asyncio.sleep(1)

        raise TextGenerationError(
            f"{self.operation_name} 처리에 실패했습니다. "
            f"role={self.role.value}, "
            f"model={config.model}, "
            f"attempts={self._max_attempts}, "
            f"last_error={last_error}"
        ) from last_error

    @abstractmethod
    def _build_prompts(
        self,
        **inputs: Any,
    ) -> TextPromptBundleProtocol:
        raise NotImplementedError

    @abstractmethod
    def _build_artifact(
        self,
        *,
        generated_text: str,
        execution_context: TextExecutionContext,
        **inputs: Any,
    ) -> ArtifactType:
        raise NotImplementedError

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        """
        역할별 입력 검증 Hook.
        """

    def _clean_generated_text(
        self,
        text: str,
    ) -> str:
        """
        모델이 전체 결과를 Markdown 코드 블록으로 감싼 경우 제거한다.
        """

        cleaned = text.strip()

        if cleaned.startswith("```markdown"):
            cleaned = cleaned[len("```markdown"):].lstrip()

            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].rstrip()

        elif cleaned.startswith("```md"):
            cleaned = cleaned[len("```md"):].lstrip()

            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].rstrip()

        return cleaned.strip()

    def _build_metadata(
        self,
        execution_context: TextExecutionContext,
    ) -> dict[str, Any]:
        metadata = execution_context.metadata

        return {
            "model": getattr(
                metadata,
                "model",
                execution_context.model,
            ),
            "attempts": getattr(
                metadata,
                "attempts",
                1,
            ),
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
            "role": execution_context.role.value,
            "response_format": (
                execution_context.response_format
            ),
            "attempt": execution_context.attempt,
        }

    def _log_completion(
        self,
        *,
        artifact: ArtifactType,
        execution_context: TextExecutionContext,
    ) -> None:
        markdown = str(
            artifact.get("markdown", "")
        )

        logger.info(
            "%s completed: chapter_id=%s model=%s "
            "attempt=%s markdown_length=%s",
            self.operation_name,
            artifact.get("chapter_id"),
            execution_context.model,
            execution_context.attempt,
            len(markdown),
        )

    def _validate_class_configuration(
        self,
    ) -> None:
        if not isinstance(
            getattr(self, "role", None),
            GenerationRole,
        ):
            raise TypeError(
                f"{type(self).__name__}.role은 "
                "GenerationRole이어야 합니다."
            )

        operation_name = str(
            getattr(
                self,
                "operation_name",
                "",
            )
        ).strip()

        if not operation_name:
            raise ValueError(
                f"{type(self).__name__}.operation_name이 "
                "필요합니다."
            )


def _extract_generated_text(
    generation_result: Any,
) -> str:
    """
    OllamaClient.generate_text() 응답 구조 차이를 흡수한다.

    우선순위:
    1. result.text
    2. result.content
    3. result.response
    4. result.data가 문자열
    5. result.data 내부의 text/content/response
    """

    for attribute_name in (
        "text",
        "content",
        "response",
    ):
        value = getattr(
            generation_result,
            attribute_name,
            None,
        )

        if isinstance(value, str) and value.strip():
            return value

    data = getattr(
        generation_result,
        "data",
        None,
    )

    if isinstance(data, str) and data.strip():
        return data

    if isinstance(data, dict):
        for key in (
            "text",
            "content",
            "response",
        ):
            value = data.get(key)

            if isinstance(value, str) and value.strip():
                return value

    raise ValueError(
        "generate_text() 결과에서 텍스트를 찾을 수 없습니다. "
        f"result_type={type(generation_result).__name__}"
    )
