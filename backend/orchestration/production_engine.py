from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlmodel import Session

from backend.agents.registry import AgentRegistry
from backend.events.event_publisher import (
    EventPublisher,
)
from backend.orchestration.handoff_manager import (
    HandoffManager,
)
from backend.orchestration.stage_runner import (
    StageRunResult,
    StageRunner,
)
from backend.services.agent_task_service import (
    AgentTaskService,
)
from backend.services.event_service import (
    EventService,
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


class ProductionEngineError(RuntimeError):
    """ProductionRun 실행 중 발생하는 기본 예외입니다."""


class ProductionRunNotFoundError(ProductionEngineError):
    """요청한 ProductionRun을 찾을 수 없을 때 발생합니다."""


class ProductionRunNotExecutableError(
    ProductionEngineError
):
    """현재 상태에서 Run을 실행할 수 없을 때 발생합니다."""


class ProductionWorkflowDeadlockError(
    ProductionEngineError
):
    """
    미완료 Stage가 남아 있는데 실행 가능한 Stage가
    하나도 없을 때 발생합니다.
    """


class ProductionStageDependencyError(
    ProductionEngineError
):
    """Stage의 dependency 정의가 잘못되었을 때 발생합니다."""


@dataclass(slots=True)
class ProductionExecutionResult:
    """ProductionEngine 전체 실행 결과입니다."""

    run_id: str
    status: str
    success: bool

    completed_stage_ids: list[str] = field(
        default_factory=list
    )

    failed_stage_ids: list[str] = field(
        default_factory=list
    )

    output_artifact_ids: list[str] = field(
        default_factory=list
    )

    stage_results: list[StageRunResult] = field(
        default_factory=list
    )

    error_message: str | None = None


class StageRunnerProtocol(Protocol):
    async def run_stage(
        self,
        *,
        stage_id: str,
    ) -> StageRunResult:
        ...


class HandoffManagerProtocol(Protocol):
    def handoff_stage_outputs(
        self,
        *,
        source_stage_id: str,
        target_stage_id: str,
    ) -> Any:
        ...


class ProductionEngine:
    """
    ProductionRun 전체를 실행하는 Orchestrator입니다.

    StageRunner / HandoffManager / AgentTaskService를
    조합하며, Prompt·LLM·Artifact 직접 생성은 하지 않습니다.
    """

    RUNNABLE_RUN_STATUSES = {
        "PENDING",
        "PAUSED",
        "FAILED",
    }

    TERMINAL_RUN_STATUSES = {
        "COMPLETED",
        "CANCELLED",
    }

    COMPLETED_STAGE_STATUS = "COMPLETED"

    FAILED_STAGE_STATUSES = {
        "FAILED",
        "CANCELLED",
    }

    PENDING_STAGE_STATUSES = {
        "PENDING",
        "READY",
        "RETRY",
    }

    def __init__(
        self,
        *,
        session: Session,
        agent_registry: AgentRegistry,
        stage_runner: StageRunnerProtocol | None = None,
        task_service: AgentTaskService | None = None,
        handoff_manager: (
            HandoffManagerProtocol | None
        ) = None,
        event_publisher: (
            EventPublisher | None
        ) = None,
    ) -> None:
        self.session = session

        self.repository = ProductionRepository(
            session
        )

        self.agent_registry = agent_registry

        self.task_service = (
            task_service
            or AgentTaskService(
                session,
                agent_registry,
            )
        )

        self.stage_runner = (
            stage_runner
            or StageRunner(
                session=session,
                agent_registry=agent_registry,
                task_service=self.task_service,
            )
        )

        self.handoff_manager = (
            handoff_manager
            or HandoffManager(session)
        )

        self.event_publisher = (
            event_publisher
            or EventPublisher(
                EventService(session)
            )
        )

    async def execute_run(
        self,
        *,
        run_id: str,
    ) -> ProductionExecutionResult:
        run = self.repository.get_run(run_id)

        if run is None:
            raise ProductionRunNotFoundError(
                "ProductionRun을 찾을 수 없습니다: "
                f"{run_id}"
            )

        self._validate_run(run)

        stage_results: list[StageRunResult] = []

        try:
            run = self._mark_run_running(run)

            self.event_publisher.run_started(run)

            while True:
                stages = self.repository.list_stages(
                    run.run_id
                )

                if not stages:
                    raise ProductionWorkflowDeadlockError(
                        "ProductionRun에 Stage가 없습니다: "
                        f"{run.run_id}"
                    )

                self._update_run_progress(
                    run=run,
                    stages=stages,
                )

                if self._all_stages_completed(stages):
                    completed_run = (
                        self._mark_run_completed(
                            run=run,
                            stages=stages,
                        )
                    )

                    output_artifact_ids = (
                        self._collect_run_outputs(
                            stages
                        )
                    )

                    self.event_publisher.run_completed(
                        completed_run,
                        output_artifact_ids=(
                            output_artifact_ids
                        ),
                    )

                    return ProductionExecutionResult(
                        run_id=completed_run.run_id,
                        status=completed_run.status,
                        success=True,
                        completed_stage_ids=[
                            stage.stage_id
                            for stage in stages
                            if self._stage_status(stage)
                            == self.COMPLETED_STAGE_STATUS
                        ],
                        failed_stage_ids=[],
                        output_artifact_ids=(
                            output_artifact_ids
                        ),
                        stage_results=stage_results,
                    )

                failed_stages = [
                    stage
                    for stage in stages
                    if self._stage_status(stage)
                    in self.FAILED_STAGE_STATUSES
                ]

                if failed_stages:
                    failed_keys = [
                        stage.stage_key
                        for stage in failed_stages
                    ]

                    raise ProductionEngineError(
                        "실패한 Stage가 있어 Run을 "
                        "계속할 수 없습니다: "
                        f"{failed_keys}"
                    )

                ready_stages = self._find_ready_stages(
                    stages
                )

                if not ready_stages:
                    raise ProductionWorkflowDeadlockError(
                        self._build_deadlock_message(
                            stages
                        )
                    )

                # 안정성을 위해 한 번에 하나의 Stage만 실행
                stage = ready_stages[0]

                run = self._set_current_stage(
                    run=run,
                    stage=stage,
                )

                self._handoff_dependencies(
                    stage=stage,
                    all_stages=stages,
                )

                task = self._ensure_stage_task(
                    run=run,
                    stage=stage,
                )

                self.handoff_manager.attach_artifacts_to_task(
                    stage_id=stage.stage_id,
                    task_id=task.task_id,
                )

                self.event_publisher.stage_started(
                    stage
                )

                try:
                    stage_result = (
                        await self.stage_runner.run_stage(
                            stage_id=stage.stage_id
                        )
                    )
                except Exception as stage_error:
                    failed_stage = (
                        self.repository.get_stage(
                            stage.stage_id
                        )
                        or stage
                    )

                    self.event_publisher.stage_failed(
                        failed_stage,
                        error=stage_error,
                    )

                    raise

                stage_results.append(stage_result)

                completed_stage = (
                    self.repository.get_stage(
                        stage.stage_id
                    )
                    or stage
                )

                self.event_publisher.stage_completed(
                    completed_stage,
                    output_artifact_ids=(
                        stage_result.output_artifact_ids
                    ),
                )

                if not stage_result.success:
                    raise ProductionEngineError(
                        "Stage 실행 결과가 "
                        "실패 상태입니다: "
                        f"{stage.stage_key}"
                    )

        except Exception as exc:
            failed_run = self._mark_run_failed(
                run=run,
                error=exc,
            )

            self.event_publisher.run_failed(
                failed_run,
                error=exc,
            )

            if isinstance(exc, ProductionEngineError):
                raise

            raise ProductionEngineError(
                "ProductionRun 실행 중 오류가 "
                "발생했습니다: "
                f"run_id={run.run_id}, "
                f"error={exc}"
            ) from exc

    async def execute_next_stage(
        self,
        *,
        run_id: str,
    ) -> StageRunResult | None:
        run = self.repository.get_run(run_id)

        if run is None:
            raise ProductionRunNotFoundError(
                "ProductionRun을 찾을 수 없습니다: "
                f"{run_id}"
            )

        if (
            self._run_status(run)
            in self.TERMINAL_RUN_STATUSES
        ):
            if self._run_status(run) == "COMPLETED":
                return None

            raise ProductionRunNotExecutableError(
                "종료된 ProductionRun은 실행할 수 "
                f"없습니다: {run.status}"
            )

        if self._run_status(run) != "RUNNING":
            run = self._mark_run_running(run)

            self.event_publisher.run_started(run)

        stages = self.repository.list_stages(
            run.run_id
        )

        if self._all_stages_completed(stages):
            self._mark_run_completed(
                run=run,
                stages=stages,
            )
            return None

        ready_stages = self._find_ready_stages(stages)

        if not ready_stages:
            raise ProductionWorkflowDeadlockError(
                self._build_deadlock_message(stages)
            )

        stage = ready_stages[0]

        run = self._set_current_stage(
            run=run,
            stage=stage,
        )

        self._handoff_dependencies(
            stage=stage,
            all_stages=stages,
        )

        task = self._ensure_stage_task(
            run=run,
            stage=stage,
        )

        self.handoff_manager.attach_artifacts_to_task(
            stage_id=stage.stage_id,
            task_id=task.task_id,
        )

        self.event_publisher.stage_started(stage)

        try:
            result = await self.stage_runner.run_stage(
                stage_id=stage.stage_id
            )
        except Exception as stage_error:
            failed_stage = (
                self.repository.get_stage(
                    stage.stage_id
                )
                or stage
            )

            self.event_publisher.stage_failed(
                failed_stage,
                error=stage_error,
            )

            failed_run = self._mark_run_failed(
                run=run,
                error=stage_error,
            )

            self.event_publisher.run_failed(
                failed_run,
                error=stage_error,
            )

            raise

        completed_stage = (
            self.repository.get_stage(
                stage.stage_id
            )
            or stage
        )

        self.event_publisher.stage_completed(
            completed_stage,
            output_artifact_ids=(
                result.output_artifact_ids
            ),
        )

        refreshed_stages = (
            self.repository.list_stages(run.run_id)
        )

        self._update_run_progress(
            run=run,
            stages=refreshed_stages,
        )

        if self._all_stages_completed(refreshed_stages):
            completed_run = (
                self._mark_run_completed(
                    run=run,
                    stages=refreshed_stages,
                )
            )

            self.event_publisher.run_completed(
                completed_run,
                output_artifact_ids=(
                    self._collect_run_outputs(
                        refreshed_stages
                    )
                ),
            )

        return result

    def _ensure_stage_task(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> AgentTask:
        existing_tasks = (
            self.repository.list_tasks_for_stage(
                stage.stage_id
            )
        )

        if existing_tasks:
            return existing_tasks[0]

        agent = (
            self.agent_registry.get_single_for_stage(
                stage.stage_type
            )
        )

        input_artifact_ids = json_loads(
            stage.input_artifact_ids_json,
            [],
        )

        return self.task_service.create_task(
            run_id=run.run_id,
            stage_id=stage.stage_id,
            book_id=stage.book_id,
            unit_id=stage.unit_id,
            agent_role=agent.role,
            agent_name=agent.name,
            task_type=f"EXECUTE_{stage.stage_type}",
            input_artifact_ids=input_artifact_ids,
        )

    def _find_ready_stages(
        self,
        stages: list[ProductionStage],
    ) -> list[ProductionStage]:
        stages_by_id = {
            stage.stage_id: stage
            for stage in stages
        }

        stages_by_key = {
            stage.stage_key: stage
            for stage in stages
        }

        ready: list[ProductionStage] = []

        for stage in stages:
            if (
                self._stage_status(stage)
                not in self.PENDING_STAGE_STATUSES
            ):
                continue

            dependency_refs = self._get_dependency_refs(
                stage
            )

            dependencies = self._resolve_dependencies(
                stage=stage,
                dependency_refs=dependency_refs,
                stages_by_id=stages_by_id,
                stages_by_key=stages_by_key,
            )

            if all(
                self._stage_status(dependency)
                == self.COMPLETED_STAGE_STATUS
                for dependency in dependencies
            ):
                ready.append(stage)

        return sorted(
            ready,
            key=lambda item: (
                item.order_index,
                item.created_at,
            ),
        )

    def _handoff_dependencies(
        self,
        *,
        stage: ProductionStage,
        all_stages: list[ProductionStage],
    ) -> None:
        stages_by_id = {
            item.stage_id: item
            for item in all_stages
        }

        stages_by_key = {
            item.stage_key: item
            for item in all_stages
        }

        dependency_refs = self._get_dependency_refs(
            stage
        )

        dependencies = self._resolve_dependencies(
            stage=stage,
            dependency_refs=dependency_refs,
            stages_by_id=stages_by_id,
            stages_by_key=stages_by_key,
        )

        for dependency in dependencies:
            if (
                self._stage_status(dependency)
                != self.COMPLETED_STAGE_STATUS
            ):
                raise ProductionStageDependencyError(
                    "완료되지 않은 dependency를 "
                    "Handoff할 수 없습니다: "
                    f"from={dependency.stage_key}, "
                    f"to={stage.stage_key}"
                )

            self.handoff_manager.handoff_stage_outputs(
                source_stage_id=dependency.stage_id,
                target_stage_id=stage.stage_id,
            )

    def _resolve_dependencies(
        self,
        *,
        stage: ProductionStage,
        dependency_refs: list[str],
        stages_by_id: dict[str, ProductionStage],
        stages_by_key: dict[str, ProductionStage],
    ) -> list[ProductionStage]:
        dependencies: list[ProductionStage] = []

        for reference in dependency_refs:
            dependency = stages_by_id.get(reference)

            if dependency is None:
                dependency = stages_by_key.get(
                    reference
                )

            if dependency is None:
                raise ProductionStageDependencyError(
                    "Stage dependency를 찾을 수 "
                    f"없습니다: "
                    f"stage={stage.stage_key}, "
                    f"dependency={reference}"
                )

            if dependency.stage_id == stage.stage_id:
                raise ProductionStageDependencyError(
                    "Stage는 자기 자신을 dependency로 "
                    f"가질 수 없습니다: "
                    f"{stage.stage_key}"
                )

            dependencies.append(dependency)

        return dependencies

    @staticmethod
    def _get_dependency_refs(
        stage: ProductionStage,
    ) -> list[str]:
        values = json_loads(
            stage.depends_on_json,
            [],
        )

        if not isinstance(values, list):
            raise ProductionStageDependencyError(
                "depends_on_json은 list여야 "
                f"합니다: stage={stage.stage_key}"
            )

        return [
            str(value)
            for value in values
            if value
        ]

    def _validate_run(
        self,
        run: ProductionRun,
    ) -> None:
        status = self._run_status(run)

        if status == "RUNNING":
            raise ProductionRunNotExecutableError(
                "이미 실행 중인 ProductionRun입니다: "
                f"{run.run_id}"
            )

        if status in self.TERMINAL_RUN_STATUSES:
            raise ProductionRunNotExecutableError(
                "종료된 ProductionRun은 다시 실행할 수 "
                f"없습니다: status={status}"
            )

        if status not in self.RUNNABLE_RUN_STATUSES:
            raise ProductionRunNotExecutableError(
                "현재 상태에서는 ProductionRun을 실행할 "
                f"수 없습니다: status={status}"
            )

    def _mark_run_running(
        self,
        run: ProductionRun,
    ) -> ProductionRun:
        run.status = "RUNNING"
        run.current_stage_id = None
        run.error_json = "{}"
        run.completed_at = None

        if run.started_at is None:
            run.started_at = utc_now()

        return self.repository.save_run(run)

    def _set_current_stage(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> ProductionRun:
        run.current_stage_id = stage.stage_id
        return self.repository.save_run(run)

    def _mark_run_completed(
        self,
        *,
        run: ProductionRun,
        stages: list[ProductionStage],
    ) -> ProductionRun:
        output_artifact_ids = (
            self._collect_run_outputs(stages)
        )

        run.status = "COMPLETED"
        run.current_stage_id = None
        run.completed_at = utc_now()

        run.completed_stages = len(
            [
                stage
                for stage in stages
                if self._stage_status(stage)
                == self.COMPLETED_STAGE_STATUS
            ]
        )

        run.failed_stages = 0

        run.result_json = json_dumps(
            {
                "output_artifact_ids": (
                    output_artifact_ids
                ),
                "completed_stage_ids": [
                    stage.stage_id
                    for stage in stages
                    if self._stage_status(stage)
                    == self.COMPLETED_STAGE_STATUS
                ],
            }
        )

        run.error_json = "{}"

        return self.repository.save_run(run)

    def _mark_run_failed(
        self,
        *,
        run: ProductionRun,
        error: Exception,
    ) -> ProductionRun:
        stages = self.repository.list_stages(
            run.run_id
        )

        run.status = "FAILED"
        run.current_stage_id = None
        run.completed_at = utc_now()

        run.completed_stages = len(
            [
                stage
                for stage in stages
                if self._stage_status(stage)
                == self.COMPLETED_STAGE_STATUS
            ]
        )

        run.failed_stages = len(
            [
                stage
                for stage in stages
                if self._stage_status(stage)
                in self.FAILED_STAGE_STATUSES
            ]
        )

        run.error_json = json_dumps(
            {
                "type": type(error).__name__,
                "message": str(error),
            }
        )

        return self.repository.save_run(run)

    def _update_run_progress(
        self,
        *,
        run: ProductionRun,
        stages: list[ProductionStage],
    ) -> ProductionRun:
        run.total_stages = len(stages)

        run.completed_stages = len(
            [
                stage
                for stage in stages
                if self._stage_status(stage)
                == self.COMPLETED_STAGE_STATUS
            ]
        )

        run.failed_stages = len(
            [
                stage
                for stage in stages
                if self._stage_status(stage)
                in self.FAILED_STAGE_STATUSES
            ]
        )

        return self.repository.save_run(run)

    @classmethod
    def _all_stages_completed(
        cls,
        stages: list[ProductionStage],
    ) -> bool:
        return bool(stages) and all(
            cls._stage_status(stage)
            == cls.COMPLETED_STAGE_STATUS
            for stage in stages
        )

    @staticmethod
    def _collect_run_outputs(
        stages: list[ProductionStage],
    ) -> list[str]:
        result: list[str] = []

        for stage in sorted(
            stages,
            key=lambda item: (
                item.order_index,
                item.created_at,
            ),
        ):
            artifact_ids = json_loads(
                stage.output_artifact_ids_json,
                [],
            )

            for artifact_id in artifact_ids:
                artifact_id = str(artifact_id)

                if artifact_id not in result:
                    result.append(artifact_id)

        return result

    @classmethod
    def _build_deadlock_message(
        cls,
        stages: list[ProductionStage],
    ) -> str:
        details: list[dict[str, Any]] = []

        for stage in stages:
            if (
                cls._stage_status(stage)
                == cls.COMPLETED_STAGE_STATUS
            ):
                continue

            details.append(
                {
                    "stage_key": stage.stage_key,
                    "status": cls._stage_status(
                        stage
                    ),
                    "depends_on": json_loads(
                        stage.depends_on_json,
                        [],
                    ),
                }
            )

        return (
            "실행 가능한 Stage가 없습니다. "
            "dependency 순환, 잘못된 dependency 또는 "
            "선행 Stage 실패 여부를 확인하세요. "
            f"미완료 Stage: {details}"
        )

    @staticmethod
    def _run_status(run: ProductionRun) -> str:
        return ProductionEngine._normalize_status(
            run.status
        )

    @staticmethod
    def _stage_status(stage: ProductionStage) -> str:
        return ProductionEngine._normalize_status(
            stage.status
        )

    @staticmethod
    def _normalize_status(value: Any) -> str:
        enum_value = getattr(value, "value", value)

        return str(enum_value).strip().upper()
