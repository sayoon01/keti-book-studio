from __future__ import annotations

from sqlmodel import Session

from backend.agents.context import AgentContext
from backend.agents.registry import (
    AgentRegistry,
)
from backend.agents.schemas import (
    AgentExecutionStatus,
    AgentResult,
)
from backend.publishing.enums import (
    AgentTaskStatus,
    PublishingEventType,
)
from backend.services.artifact_service import (
    ArtifactService,
)
from backend.storage.model_utils import (
    json_dumps,
    utc_now,
)
from backend.storage.models_publishing import (
    AgentTask,
    PublishingEvent,
)
from backend.storage.repositories.event_repository import (
    EventRepository,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class AgentTaskService:
    def __init__(
        self,
        session: Session,
        registry: AgentRegistry,
    ):
        self.session = session
        self.registry = registry

        self.repository = ProductionRepository(
            session
        )

        self.event_repository = (
            EventRepository(session)
        )

        self.artifact_service = (
            ArtifactService(session)
        )

    def create_task(
        self,
        *,
        run_id: str,
        stage_id: str,
        book_id: str,
        unit_id: str | None,
        agent_role: str,
        agent_name: str,
        task_type: str,
        priority: int = 0,
        input_artifact_ids: list[str] | None = None,
        input_data: dict | None = None,
        max_retries: int = 1,
    ) -> AgentTask:
        run = self.repository.get_run(run_id)

        if not run:
            raise ValueError(
                "ProductionRun을 찾을 수 없습니다."
            )

        stage = self.repository.get_stage(
            stage_id
        )

        if not stage:
            raise ValueError(
                "ProductionStage를 찾을 수 없습니다."
            )

        if stage.run_id != run_id:
            raise ValueError(
                "Stage와 Run이 일치하지 않습니다."
            )

        if stage.book_id != book_id:
            raise ValueError(
                "Stage와 Book이 일치하지 않습니다."
            )

        agent = self.registry.get_by_role(
            agent_role
        )

        if agent.name != agent_name:
            raise ValueError(
                "등록된 Agent 이름과 요청한 "
                "Agent 이름이 일치하지 않습니다."
            )

        if not agent.can_handle(
            stage.stage_type
        ):
            raise ValueError(
                f"{agent_role} Agent는 "
                f"{stage.stage_type} Stage를 "
                "처리할 수 없습니다."
            )

        task = AgentTask(
            run_id=run_id,
            stage_id=stage_id,
            book_id=book_id,
            unit_id=unit_id,
            agent_role=agent_role,
            agent_name=agent_name,
            task_type=task_type,
            status=AgentTaskStatus.READY.value,
            priority=priority,
            input_artifact_ids_json=json_dumps(
                input_artifact_ids or []
            ),
            input_json=json_dumps(
                input_data or {}
            ),
            max_retries=max_retries,
        )

        task = self.repository.add_task(task)

        self.event_repository.add_event(
            PublishingEvent(
                run_id=run_id,
                stage_id=stage_id,
                task_id=task.task_id,
                book_id=book_id,
                unit_id=unit_id,
                event_type=(
                    PublishingEventType
                    .TASK_CREATED
                    .value
                ),
                actor_type="SYSTEM",
                actor_id=agent_role,
                title="Agent Task 생성",
                message=(
                    f"{agent_name} Task가 "
                    "생성되었습니다."
                ),
                payload_json=json_dumps(
                    {
                        "agent_role": agent_role,
                        "task_type": task_type,
                    }
                ),
            )
        )

        return task

    async def execute_task(
        self,
        *,
        task_id: str,
        context: AgentContext,
    ) -> AgentResult:
        task = self.repository.get_task(
            task_id
        )

        if not task:
            raise ValueError(
                "AgentTask를 찾을 수 없습니다."
            )

        self._validate_task_context(
            task,
            context,
        )

        if task.status not in {
            AgentTaskStatus.READY.value,
            AgentTaskStatus.PENDING.value,
            AgentTaskStatus.FAILED.value,
        }:
            raise ValueError(
                "현재 상태에서는 Task를 실행할 "
                f"수 없습니다: {task.status}"
            )

        agent = self.registry.get_by_role(
            task.agent_role
        )

        task.status = (
            AgentTaskStatus.RUNNING.value
        )

        task.attempt += 1
        task.started_at = utc_now()

        task = self.repository.save_task(task)

        self.event_repository.add_event(
            PublishingEvent(
                run_id=task.run_id,
                stage_id=task.stage_id,
                task_id=task.task_id,
                book_id=task.book_id,
                unit_id=task.unit_id,
                event_type=(
                    PublishingEventType
                    .TASK_STARTED
                    .value
                ),
                actor_type="AGENT",
                actor_id=task.agent_role,
                title="Agent Task 시작",
                message=(
                    f"{task.agent_name} 실행을 "
                    "시작했습니다."
                ),
                payload_json=json_dumps(
                    {
                        "attempt": task.attempt,
                    }
                ),
            )
        )

        result = await agent.execute(context)

        task.output_json = json_dumps(
            result.output_data
        )

        task.runtime_state_json = json_dumps(
            result.runtime_state
        )

        task.model_name = (
            result.usage.model_name
        )

        task.prompt_tokens = (
            result.usage.prompt_tokens
        )

        task.completion_tokens = (
            result.usage.completion_tokens
        )

        task.total_tokens = (
            result.usage.total_tokens
        )

        task.latency_ms = (
            result.usage.latency_ms
        )

        if result.status in {
            AgentExecutionStatus.SUCCESS,
            AgentExecutionStatus.PARTIAL,
        }:
            records = (
                self.artifact_service
                .create_many(
                    run_id=task.run_id,
                    book_id=task.book_id,
                    stage_id=task.stage_id,
                    task_id=task.task_id,
                    unit_id=task.unit_id,
                    artifacts=result.artifacts,
                    created_by_role=(
                        task.agent_role
                    ),
                )
            )

            if (
                result.status
                == AgentExecutionStatus.SUCCESS
            ):
                task.status = (
                    AgentTaskStatus
                    .COMPLETED
                    .value
                )
            else:
                task.status = (
                    AgentTaskStatus
                    .PARTIAL
                    .value
                )

            task.completed_at = utc_now()

            task = self.repository.save_task(
                task
            )

            self.event_repository.add_event(
                PublishingEvent(
                    run_id=task.run_id,
                    stage_id=task.stage_id,
                    task_id=task.task_id,
                    book_id=task.book_id,
                    unit_id=task.unit_id,
                    event_type=(
                        PublishingEventType
                        .TASK_COMPLETED
                        .value
                    ),
                    actor_type="AGENT",
                    actor_id=task.agent_role,
                    title="Agent Task 완료",
                    message=result.summary,
                    payload_json=json_dumps(
                        {
                            "status": (
                                result.status.value
                            ),
                            "artifact_ids": [
                                record.artifact_id
                                for record
                                in records
                            ],
                            "warnings": (
                                result.warnings
                            ),
                        }
                    ),
                )
            )

        elif (
            result.status
            == AgentExecutionStatus.WAITING
        ):
            task.status = (
                AgentTaskStatus.WAITING.value
            )

            task = self.repository.save_task(
                task
            )

        elif (
            result.status
            == AgentExecutionStatus.SKIPPED
        ):
            task.status = (
                AgentTaskStatus.CANCELLED.value
            )

            task.completed_at = utc_now()

            task = self.repository.save_task(
                task
            )

        else:
            task.status = (
                AgentTaskStatus.FAILED.value
            )

            task.error_json = json_dumps(
                {
                    "summary": result.summary,
                    "errors": result.errors,
                }
            )

            task.completed_at = utc_now()

            task = self.repository.save_task(
                task
            )

            self.event_repository.add_event(
                PublishingEvent(
                    run_id=task.run_id,
                    stage_id=task.stage_id,
                    task_id=task.task_id,
                    book_id=task.book_id,
                    unit_id=task.unit_id,
                    event_type=(
                        PublishingEventType
                        .TASK_FAILED
                        .value
                    ),
                    actor_type="AGENT",
                    actor_id=task.agent_role,
                    title="Agent Task 실패",
                    message=result.summary,
                    payload_json=json_dumps(
                        {
                            "errors": (
                                result.errors
                            ),
                            "attempt": (
                                task.attempt
                            ),
                        }
                    ),
                    severity="ERROR",
                )
            )

        return result

    def _validate_task_context(
        self,
        task: AgentTask,
        context: AgentContext,
    ) -> None:
        runtime = context.runtime

        checks = {
            "run_id": (
                task.run_id,
                runtime.run_id,
            ),
            "stage_id": (
                task.stage_id,
                runtime.stage_id,
            ),
            "task_id": (
                task.task_id,
                runtime.task_id,
            ),
            "agent_role": (
                task.agent_role,
                runtime.agent_role,
            ),
            "agent_name": (
                task.agent_name,
                runtime.agent_name,
            ),
        }

        mismatches = [
            field_name
            for field_name, (
                expected,
                actual,
            ) in checks.items()
            if expected != actual
        ]

        if mismatches:
            raise ValueError(
                "AgentContext가 AgentTask와 "
                "일치하지 않습니다: "
                + ", ".join(mismatches)
            )
