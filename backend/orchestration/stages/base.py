from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter

from backend.orchestration.context import AgentContext
from backend.orchestration.agent_schemas import (
    AgentExecutionStatus,
    AgentResult,
)


class BasePublishingAgent(ABC):
    """
    모든 Publishing Agent의 공통 기반 클래스입니다.

    실제 Agent는 _run()만 구현합니다.
    """

    role: str
    name: str

    supported_stage_types: set[str]

    required_artifact_types: set[str] = set()
    output_artifact_types: set[str] = set()

    def __init__(
        self,
        *,
        role: str,
        name: str,
        supported_stage_types: set[str],
        required_artifact_types: set[str] | None = None,
        output_artifact_types: set[str] | None = None,
    ):
        self.role = role
        self.name = name

        self.supported_stage_types = (
            supported_stage_types
        )

        self.required_artifact_types = (
            required_artifact_types or set()
        )

        self.output_artifact_types = (
            output_artifact_types or set()
        )

    async def execute(
        self,
        context: AgentContext,
    ) -> AgentResult:
        started_at = perf_counter()

        try:
            self._validate_context(context)

            await self.before_execute(context)

            result = await self._run(context)

            self._validate_result(result)

            elapsed_ms = int(
                (perf_counter() - started_at) * 1000
            )

            if result.usage.latency_ms <= 0:
                result.usage.latency_ms = elapsed_ms

            await self.after_execute(
                context,
                result,
            )

            return result

        except Exception as exc:
            elapsed_ms = int(
                (perf_counter() - started_at) * 1000
            )

            return AgentResult.failed(
                summary=(
                    f"{self.name} 실행 중 오류가 "
                    "발생했습니다."
                ),
                errors=[
                    f"{type(exc).__name__}: {exc}"
                ],
                runtime_state={
                    "agent_role": self.role,
                    "agent_name": self.name,
                    "latency_ms": elapsed_ms,
                },
            )

    def can_handle(
        self,
        stage_type: str,
    ) -> bool:
        return (
            stage_type
            in self.supported_stage_types
        )

    def _validate_context(
        self,
        context: AgentContext,
    ) -> None:
        if not self.can_handle(
            context.runtime.stage_type
        ):
            raise ValueError(
                f"{self.name}은 Stage Type "
                f"{context.runtime.stage_type}을 "
                "처리할 수 없습니다."
            )

        if (
            context.runtime.agent_role
            != self.role
        ):
            raise ValueError(
                "AgentContext의 agent_role과 "
                "Agent의 role이 일치하지 않습니다."
            )

        available_artifact_types = {
            artifact.artifact_type
            for artifact
            in context.input_artifacts
        }

        missing_types = (
            self.required_artifact_types
            - available_artifact_types
        )

        if missing_types:
            missing_text = ", ".join(
                sorted(missing_types)
            )

            raise ValueError(
                "필수 입력 Artifact가 없습니다: "
                f"{missing_text}"
            )

    def _validate_result(
        self,
        result: AgentResult,
    ) -> None:
        if not isinstance(result, AgentResult):
            raise TypeError(
                "Agent는 반드시 AgentResult를 "
                "반환해야 합니다."
            )

        if (
            result.status
            == AgentExecutionStatus.SUCCESS
            and self.output_artifact_types
        ):
            produced_types = {
                artifact.artifact_type
                for artifact in result.artifacts
            }

            missing_outputs = (
                self.output_artifact_types
                - produced_types
            )

            if missing_outputs:
                output_text = ", ".join(
                    sorted(missing_outputs)
                )

                raise ValueError(
                    "성공 결과에 필수 출력 Artifact가 "
                    f"없습니다: {output_text}"
                )

    async def before_execute(
        self,
        context: AgentContext,
    ) -> None:
        return None

    async def after_execute(
        self,
        context: AgentContext,
        result: AgentResult,
    ) -> None:
        return None

    @abstractmethod
    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        raise NotImplementedError
