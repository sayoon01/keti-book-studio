from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
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


class StructuredGenerationError(RuntimeError):
    """
    구조화된 JSON Artifact 생성에 실패했을 때 발생한다.
    """


class PromptBundleProtocol(Protocol):
    """
    역할별 PromptBundle이 만족해야 하는 최소 인터페이스.

    ResearcherPromptBundle, ReviewerPromptBundle 등이
    이 Protocol을 별도 상속하지 않아도 구조적으로 호환된다.
    """

    system_prompt: str
    user_prompt: str


ArtifactType = TypeVar(
    "ArtifactType",
    bound=dict[str, Any],
)


ArtifactValidator = Callable[
    [dict[str, Any]],
    ArtifactType,
]


@dataclass(frozen=True, slots=True)
class StructuredExecutionContext:
    """
    Base Handler가 결과 보정 단계에 전달하는 실행 정보.
    """

    role: GenerationRole
    model: str
    response_format: str
    attempt: int
    metadata: Any


class BaseStructuredHandler(
    ABC,
    Generic[ArtifactType],
):
    """
    JSON Artifact를 생성하는 역할의 공통 Base Handler.

    Template Method 패턴을 사용한다.

    Base가 담당하는 것:
    - ModelRouter 조회
    - 역할 활성화 확인
    - Ollama JSON 호출
    - 재시도
    - 공통 metadata
    - Validator 실행
    - 공통 오류 처리

    하위 클래스가 담당하는 것:
    - role
    - operation_name
    - validator
    - Prompt 생성
    - 역할별 결과 보정
    - 역할별 입력 검증
    """

    role: GenerationRole
    operation_name: str
    validator: ArtifactValidator[ArtifactType]

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
        역할별 Handler가 호출하는 공통 실행 메서드.

        실행 순서:
        1. 입력 검증
        2. 프롬프트 생성
        3. 모델 설정 조회
        4. Ollama JSON 호출
        5. payload 보정
        6. Validator 실행
        7. Artifact 반환
        """

        self._validate_inputs(**inputs)

        prompts = self._build_prompts(**inputs)

        if not prompts.system_prompt.strip():
            raise StructuredGenerationError(
                f"{self.operation_name} system_prompt가 비어 있습니다."
            )

        if not prompts.user_prompt.strip():
            raise StructuredGenerationError(
                f"{self.operation_name} user_prompt가 비어 있습니다."
            )

        config = self._model_router.get_config(
            self.role
        )

        if not config.enabled:
            raise StructuredGenerationError(
                f"{self.role.value} 역할이 비활성화되어 있습니다."
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
                    await self._client.generate_json(
                        model=config.model,
                        system_prompt=prompts.system_prompt,
                        user_prompt=prompts.user_prompt,
                        temperature=config.temperature,
                        num_predict=config.num_predict,
                        num_ctx=config.num_ctx,
                        timeout_seconds=(
                            config.timeout_seconds
                        ),
                    )
                )

                raw_payload = dict(
                    generation_result.data
                )

                execution_context = (
                    StructuredExecutionContext(
                        role=self.role,
                        model=config.model,
                        response_format=(
                            config.response_format
                        ),
                        attempt=attempt,
                        metadata=(
                            generation_result.metadata
                        ),
                    )
                )

                enriched_payload = (
                    self._enrich_payload(
                        payload=raw_payload,
                        execution_context=(
                            execution_context
                        ),
                        **inputs,
                    )
                )

                if not isinstance(
                    enriched_payload,
                    dict,
                ):
                    raise TypeError(
                        "_enrich_payload()는 dictionary를 "
                        "반환해야 합니다."
                    )

                validated_artifact = self.validator(
                    enriched_payload
                )

                self._log_completion(
                    artifact=validated_artifact,
                    execution_context=(
                        execution_context
                    ),
                )

                return validated_artifact

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

        raise StructuredGenerationError(
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
    ) -> PromptBundleProtocol:
        """
        역할별 PromptBundle을 생성한다.
        """

        raise NotImplementedError

    @abstractmethod
    def _enrich_payload(
        self,
        *,
        payload: dict[str, Any],
        execution_context: StructuredExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        """
        LLM 결과에 정본 chapter_id, title, metadata 등을 추가한다.
        """

        raise NotImplementedError

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        """
        역할별 입력 검증 Hook.

        별도 검증이 필요하지 않은 Handler는 구현하지 않아도 된다.
        """

    def _log_completion(
        self,
        *,
        artifact: ArtifactType,
        execution_context: StructuredExecutionContext,
    ) -> None:
        """
        기본 완료 로그.

        역할별 세부 로그가 필요한 경우 하위 클래스에서 재정의한다.
        """

        logger.info(
            "%s completed: model=%s attempt=%s "
            "artifact_type=%s chapter_id=%s",
            self.operation_name,
            execution_context.model,
            execution_context.attempt,
            artifact.get("artifact_type"),
            artifact.get("chapter_id"),
        )

    def _build_metadata(
        self,
        execution_context: StructuredExecutionContext,
    ) -> dict[str, Any]:
        """
        Ollama metadata와 Generation 역할 정보를 조립한다.
        """

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

    def _validate_class_configuration(
        self,
    ) -> None:
        """
        하위 Handler의 필수 클래스 설정을 시작 시점에 검증한다.
        """

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

        validator = getattr(
            self,
            "validator",
            None,
        )

        if not callable(validator):
            raise TypeError(
                f"{type(self).__name__}.validator는 "
                "호출 가능한 함수여야 합니다."
            )
