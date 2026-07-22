from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlmodel import Session

from backend.agents.context import AgentContext
from backend.agents.context_builder import (
    AgentContextBuilder,
)
from backend.agents.registry import AgentRegistry
from backend.agents.schemas import (
    AgentExecutionStatus,
    AgentResult,
)
from backend.publishing.enums import (
    ProductionStageType,
)
from backend.services.agent_task_service import (
    AgentTaskService,
)
from backend.storage.model_utils import (
    json_dumps,
    json_loads,
    utc_now,
)
from backend.storage.models_publishing import (
    AgentTask,
    ProductionRun,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class StageRunnerError(RuntimeError):
    """Stage 실행 중 발생하는 기본 예외입니다."""


class StageNotFoundError(StageRunnerError):
    """ProductionStage를 찾을 수 없을 때 발생합니다."""


class RunNotFoundError(StageRunnerError):
    """ProductionRun을 찾을 수 없을 때 발생합니다."""


class StageNotRunnableError(StageRunnerError):
    """현재 상태에서 실행할 수 없는 Stage일 때 발생합니다."""


class StageTaskNotFoundError(StageRunnerError):
    """Stage에 실행할 AgentTask가 없을 때 발생합니다."""


class StageExecutionFailedError(StageRunnerError):
    """AgentTask 실행이 실패했을 때 발생합니다."""


@dataclass(slots=True)
class StageRunResult:
    """StageRunner가 Stage 하나를 실행한 결과입니다."""

    run_id: str
    stage_id: str
    stage_key: str
    stage_type: str

    task_id: str | None

    status: str
    success: bool

    output_artifact_ids: list[str]

    agent_result: AgentResult | None = None
    error_message: str | None = None


class StageExecutionAdapterProtocol(Protocol):
    def get_or_create_task(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> AgentTask:
        ...

    async def execute_task(
        self,
        *,
        task: AgentTask,
        context: AgentContext,
    ) -> AgentResult:
        ...

    def get_output_artifact_ids(
        self,
        *,
        task: AgentTask,
    ) -> list[str]:
        ...


class StageExecutionAdapter:
    """
    기존 AgentTaskService를 StageRunner에서 사용하기 위한 Adapter입니다.
    """

    def __init__(
        self,
        *,
        session: Session,
        task_service: AgentTaskService,
        repository: ProductionRepository,
    ) -> None:
        self.session = session
        self.task_service = task_service
        self.repository = repository

    def get_or_create_task(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> AgentTask:
        tasks = self.repository.list_tasks_for_stage(
            stage.stage_id
        )

        if not tasks:
            raise StageTaskNotFoundError(
                "Stage에 등록된 AgentTask가 없습니다: "
                f"stage_id={stage.stage_id}, "
                f"stage_key={stage.stage_key}"
            )

        return tasks[0]

    async def execute_task(
        self,
        *,
        task: AgentTask,
        context: AgentContext,
    ) -> AgentResult:
        result = self.task_service.execute_task(
            task_id=task.task_id,
            context=context,
        )

        if hasattr(result, "__await__"):
            result = await result

        if not isinstance(result, AgentResult):
            raise StageRunnerError(
                "AgentTaskService 실행 결과가 "
                "AgentResult가 아닙니다: "
                f"{type(result).__name__}"
            )

        return result

    def get_output_artifact_ids(
        self,
        *,
        task: AgentTask,
    ) -> list[str]:
        refreshed_task = self.repository.get_task(
            task.task_id
        )

        if refreshed_task is None:
            return []

        values = json_loads(
            refreshed_task.output_artifact_ids_json,
            [],
        )

        return [str(value) for value in values]


class StageRunner:
    """
    ProductionStage 하나를 실행하는 Orchestrator입니다.

    Stage 상태 전환과 Task 실행까지만 담당합니다.
    Workflow 순서·Handoff·LLM은 다루지 않습니다.
    """

    RUNNABLE_STATUSES = {
        "PENDING",
        "READY",
        "RETRY",
        "FAILED",
    }

    SUCCESS_STATUSES = {
        AgentExecutionStatus.SUCCESS.value,
        AgentExecutionStatus.PARTIAL.value,
        "COMPLETED",
    }

    def __init__(
        self,
        *,
        session: Session,
        agent_registry: AgentRegistry,
        context_builder: AgentContextBuilder | None = None,
        task_service: AgentTaskService | None = None,
        execution_adapter: (
            StageExecutionAdapterProtocol | None
        ) = None,
    ) -> None:
        self.session = session

        self.repository = ProductionRepository(
            session
        )

        self.agent_registry = agent_registry

        self.context_builder = (
            context_builder
            or AgentContextBuilder(session)
        )

        self.task_service = (
            task_service
            or AgentTaskService(
                session,
                agent_registry,
            )
        )

        self.execution_adapter = (
            execution_adapter
            or StageExecutionAdapter(
                session=session,
                task_service=self.task_service,
                repository=self.repository,
            )
        )

    async def run_stage(
        self,
        *,
        stage_id: str,
    ) -> StageRunResult:
        stage = self.repository.get_stage(
            stage_id
        )

        if stage is None:
            raise StageNotFoundError(
                "ProductionStage를 찾을 수 없습니다: "
                f"{stage_id}"
            )

        run = self.repository.get_run(
            stage.run_id
        )

        if run is None:
            raise RunNotFoundError(
                "ProductionRun을 찾을 수 없습니다: "
                f"{stage.run_id}"
            )

        self._validate_stage(stage=stage)

        task: AgentTask | None = None

        try:
            self._mark_stage_running(stage)

            task = (
                self.execution_adapter
                .get_or_create_task(
                    run=run,
                    stage=stage,
                )
            )

            context = self._build_context(
                task=task,
                stage=stage,
                run=run,
            )

            result = await (
                self.execution_adapter
                .execute_task(
                    task=task,
                    context=context,
                )
            )

            if not self._is_agent_result_success(
                result
            ):
                error_message = self._get_result_error(
                    result
                )

                raise StageExecutionFailedError(
                    error_message
                )

            output_artifact_ids = (
                self.execution_adapter
                .get_output_artifact_ids(
                    task=task
                )
            )

            self._mark_stage_completed(stage=stage)

            return StageRunResult(
                run_id=run.run_id,
                stage_id=stage.stage_id,
                stage_key=stage.stage_key,
                stage_type=stage.stage_type,
                task_id=task.task_id,
                status="COMPLETED",
                success=True,
                output_artifact_ids=(
                    output_artifact_ids
                ),
                agent_result=result,
            )

        except Exception as exc:
            self._mark_stage_failed(
                stage=stage,
                error_message=str(exc),
            )

            if isinstance(exc, StageRunnerError):
                raise

            raise StageExecutionFailedError(
                "Stage 실행 중 오류가 발생했습니다: "
                f"stage_id={stage.stage_id}, "
                f"error={exc}"
            ) from exc

    def _validate_stage(
        self,
        *,
        stage: ProductionStage,
    ) -> None:
        status = self._normalize_status(
            getattr(stage, "status", "PENDING")
        )

        if status == "COMPLETED":
            raise StageNotRunnableError(
                "이미 완료된 Stage입니다: "
                f"{stage.stage_id}"
            )

        if status == "RUNNING":
            raise StageNotRunnableError(
                "이미 실행 중인 Stage입니다: "
                f"{stage.stage_id}"
            )

        if status not in self.RUNNABLE_STATUSES:
            raise StageNotRunnableError(
                "현재 상태에서는 Stage를 실행할 수 "
                f"없습니다: status={status}, "
                f"stage_id={stage.stage_id}"
            )

        supported_stage_types = {
            stage_type.value
            for stage_type in ProductionStageType
        }

        if stage.stage_type not in supported_stage_types:
            raise StageNotRunnableError(
                "지원하지 않는 StageType입니다: "
                f"{stage.stage_type}"
            )

    def _build_context(
        self,
        *,
        task: AgentTask,
        stage: ProductionStage,
        run: ProductionRun,
    ) -> AgentContext:
        build_method = getattr(
            self.context_builder,
            "build_for_task",
            None,
        )

        if build_method is None:
            build_method = getattr(
                self.context_builder,
                "build",
                None,
            )

        if build_method is None:
            build_method = getattr(
                self.context_builder,
                "build_context",
                None,
            )

        if build_method is None:
            raise StageRunnerError(
                "AgentContextBuilder에 "
                "build_for_task() / build() / "
                "build_context() 메서드가 없습니다."
            )

        context = build_method(
            task_id=task.task_id,
        )

        if not isinstance(context, AgentContext):
            raise StageRunnerError(
                "AgentContextBuilder 결과가 "
                "AgentContext가 아닙니다: "
                f"{type(context).__name__}"
            )

        return context

    def _mark_stage_running(
        self,
        stage: ProductionStage,
    ) -> None:
        self._set_stage_status(
            stage=stage,
            status="RUNNING",
            error_message=None,
        )

        stage.started_at = utc_now()
        self.repository.save_stage(stage)

    def _mark_stage_completed(
        self,
        *,
        stage: ProductionStage,
    ) -> None:
        self._set_stage_status(
            stage=stage,
            status="COMPLETED",
            error_message=None,
        )

        stage.completed_at = utc_now()
        self.repository.save_stage(stage)

    def _mark_stage_failed(
        self,
        *,
        stage: ProductionStage,
        error_message: str,
    ) -> None:
        self._set_stage_status(
            stage=stage,
            status="FAILED",
            error_message=error_message,
        )

        stage.completed_at = utc_now()
        self.repository.save_stage(stage)

    @staticmethod
    def _set_stage_status(
        *,
        stage: ProductionStage,
        status: str,
        error_message: str | None,
    ) -> None:
        stage.status = status

        if hasattr(stage, "error_json"):
            if error_message:
                stage.error_json = json_dumps(
                    {"message": error_message}
                )
            else:
                stage.error_json = "{}"
        elif hasattr(stage, "error_message"):
            stage.error_message = error_message
        elif hasattr(stage, "error"):
            stage.error = error_message
        elif hasattr(stage, "last_error"):
            stage.last_error = error_message

    @classmethod
    def _is_agent_result_success(
        cls,
        result: AgentResult,
    ) -> bool:
        # AgentResult.success() 클래스메서드와 혼동하지 않도록
        # bool 필드만 성공 플래그로 인정한다.
        success_attr = getattr(
            type(result),
            "model_fields",
            {},
        ).get("success")

        if success_attr is not None:
            return bool(
                getattr(result, "success")
            )

        status = cls._normalize_status(
            getattr(result, "status", "")
        )

        return status in cls.SUCCESS_STATUSES

    @staticmethod
    def _get_result_error(
        result: AgentResult,
    ) -> str:
        errors = getattr(result, "errors", None)

        if errors:
            return "; ".join(str(item) for item in errors)

        for field_name in (
            "error_message",
            "error",
            "message",
            "summary",
        ):
            value = getattr(result, field_name, None)

            if value:
                return str(value)

        return "AgentTask 실행 결과가 실패 상태입니다."

    @staticmethod
    def _normalize_status(value: Any) -> str:
        enum_value = getattr(value, "value", value)

        return str(enum_value).strip().upper()
