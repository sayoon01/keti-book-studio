from __future__ import annotations

from sqlmodel import Session

from backend.agents.registry import AgentRegistry
from backend.orchestration.publishing_agent_registry import (
    build_publishing_agent_registry,
)
from backend.orchestration.workflow_validator import (
    validate_workflow_artifact_contract,
)
from backend.publishing.enums import (
    ProductionRunStatus,
    ProductionStageStatus,
    PublishingEventType,
)
from backend.publishing.production_schemas import (
    CreateProductionRunRequest,
    ProductionRunDetailResponse,
    ProductionRunResponse,
    ProductionStageDefinition,
    ProductionStageResponse,
)
from backend.storage.model_utils import (
    json_dumps,
    json_loads,
    utc_now,
)
from backend.storage.models import BookProject
from backend.storage.models_publishing import (
    ProductionRun,
    ProductionStage,
    PublishingEvent,
)
from backend.storage.repositories.event_repository import (
    EventRepository,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class ProductionService:
    def __init__(
        self,
        session: Session,
        agent_registry: AgentRegistry | None = None,
    ):
        self.session = session
        self.repository = ProductionRepository(session)
        self.event_repository = EventRepository(session)
        self.agent_registry = (
            agent_registry
            or build_publishing_agent_registry()
        )

    def create_run(
        self,
        request: CreateProductionRunRequest,
        *,
        stages: list[ProductionStageDefinition],
    ) -> ProductionRunDetailResponse:
        book = self.session.get(
            BookProject,
            request.book_id,
        )

        if not book:
            raise ValueError(
                "BookProject를 찾을 수 없습니다."
            )

        if not stages:
            raise ValueError(
                "ProductionRun에는 최소 한 개의 Stage가 필요합니다."
            )

        self._validate_stage_definitions(stages)

        validate_workflow_artifact_contract(
            stages=stages,
            agent_registry=self.agent_registry,
        )

        run = ProductionRun(
            book_id=request.book_id,
            workspace_id=request.workspace_id,
            workflow_type=request.workflow_type,
            automation_level=request.automation_level,
            requested_by=request.requested_by,
            input_json=json_dumps(request.input_data),
            total_stages=len(stages),
            status=ProductionRunStatus.PENDING.value,
        )

        run = self.repository.add_run(run)

        stage_models = [
            ProductionStage(
                run_id=run.run_id,
                book_id=request.book_id,
                unit_id=definition.unit_id,
                stage_key=definition.stage_key,
                stage_type=definition.stage_type.value,
                order_index=definition.order_index,
                status=(
                    ProductionStageStatus.READY.value
                    if not definition.depends_on
                    else ProductionStageStatus.PENDING.value
                ),
                depends_on_json=json_dumps(
                    definition.depends_on
                ),
                input_json=json_dumps(
                    definition.metadata
                ),
                max_retries=definition.max_retries,
            )
            for definition in sorted(
                stages,
                key=lambda item: item.order_index,
            )
        ]

        stage_models = self.repository.add_stages(
            stage_models
        )

        self.event_repository.add_event(
            PublishingEvent(
                run_id=run.run_id,
                book_id=run.book_id,
                event_type=(
                    PublishingEventType.RUN_CREATED.value
                ),
                actor_type="SYSTEM",
                title="책 제작 실행 생성",
                message=(
                    f"{len(stage_models)}개 Stage가 생성되었습니다."
                ),
                payload_json=json_dumps(
                    {
                        "workflow_type": (
                            run.workflow_type
                        ),
                        "automation_level": (
                            run.automation_level
                        ),
                        "stage_count": len(
                            stage_models
                        ),
                    }
                ),
            )
        )

        for stage in stage_models:
            self.event_repository.add_event(
                PublishingEvent(
                    run_id=run.run_id,
                    stage_id=stage.stage_id,
                    book_id=run.book_id,
                    unit_id=stage.unit_id,
                    event_type=(
                        PublishingEventType
                        .STAGE_CREATED
                        .value
                    ),
                    actor_type="SYSTEM",
                    title="제작 단계 생성",
                    message=stage.stage_key,
                    payload_json=json_dumps(
                        {
                            "stage_type": (
                                stage.stage_type
                            ),
                            "order_index": (
                                stage.order_index
                            ),
                        }
                    ),
                )
            )

        return self.get_run_detail(run.run_id)

    def start_run(
        self,
        run_id: str,
    ) -> ProductionRun:
        run = self._get_required_run(run_id)

        if run.status not in {
            ProductionRunStatus.PENDING.value,
            ProductionRunStatus.PAUSED.value,
            ProductionRunStatus.WAITING.value,
        }:
            raise ValueError(
                f"현재 상태에서는 실행할 수 없습니다: {run.status}"
            )

        run.status = ProductionRunStatus.RUNNING.value
        run.started_at = run.started_at or utc_now()
        run.paused_at = None

        stages = self.repository.list_stages(run_id)

        first_ready_stage = next(
            (
                stage
                for stage in stages
                if stage.status
                == ProductionStageStatus.READY.value
            ),
            None,
        )

        if first_ready_stage:
            run.current_stage_id = (
                first_ready_stage.stage_id
            )

        run = self.repository.save_run(run)

        self.event_repository.add_event(
            PublishingEvent(
                run_id=run.run_id,
                stage_id=run.current_stage_id,
                book_id=run.book_id,
                event_type=(
                    PublishingEventType.RUN_STARTED.value
                ),
                actor_type="SYSTEM",
                title="책 제작 실행 시작",
                message="ProductionRun이 시작되었습니다.",
            )
        )

        return run

    def get_run_detail(
        self,
        run_id: str,
    ) -> ProductionRunDetailResponse:
        run = self._get_required_run(run_id)
        stages = self.repository.list_stages(run_id)

        return ProductionRunDetailResponse(
            run=self._to_run_response(run),
            stages=[
                self._to_stage_response(stage)
                for stage in stages
            ],
        )

    def _validate_stage_definitions(
        self,
        stages: list[ProductionStageDefinition],
    ) -> None:
        stage_keys = [
            stage.stage_key
            for stage in stages
        ]

        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError(
                "중복된 stage_key가 있습니다."
            )

        available_keys = set(stage_keys)

        for stage in stages:
            for dependency in stage.depends_on:
                if dependency not in available_keys:
                    raise ValueError(
                        f"존재하지 않는 선행 Stage입니다: "
                        f"{dependency}"
                    )

                if dependency == stage.stage_key:
                    raise ValueError(
                        "Stage는 자기 자신을 선행 조건으로 "
                        "가질 수 없습니다."
                    )

    def _get_required_run(
        self,
        run_id: str,
    ) -> ProductionRun:
        run = self.repository.get_run(run_id)

        if not run:
            raise ValueError(
                "ProductionRun을 찾을 수 없습니다."
            )

        return run

    def _to_run_response(
        self,
        run: ProductionRun,
    ) -> ProductionRunResponse:
        return ProductionRunResponse(
            run_id=run.run_id,
            book_id=run.book_id,
            workspace_id=run.workspace_id,
            workflow_type=run.workflow_type,
            automation_level=run.automation_level,
            status=run.status,
            current_stage_id=run.current_stage_id,
            total_stages=run.total_stages,
            completed_stages=run.completed_stages,
            failed_stages=run.failed_stages,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )

    def _to_stage_response(
        self,
        stage: ProductionStage,
    ) -> ProductionStageResponse:
        return ProductionStageResponse(
            stage_id=stage.stage_id,
            run_id=stage.run_id,
            book_id=stage.book_id,
            unit_id=stage.unit_id,
            stage_key=stage.stage_key,
            stage_type=stage.stage_type,
            order_index=stage.order_index,
            status=stage.status,
            depends_on=json_loads(
                stage.depends_on_json,
                [],
            ),
            retry_count=stage.retry_count,
            max_retries=stage.max_retries,
            created_at=stage.created_at,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
        )
