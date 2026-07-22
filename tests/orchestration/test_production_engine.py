from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlmodel import Session

from backend.orchestration.production_engine import (
    ProductionEngine,
    ProductionRunNotExecutableError,
    ProductionRunNotFoundError,
    ProductionStageDependencyError,
    ProductionWorkflowDeadlockError,
)
from backend.orchestration.publishing_agent_registry import (
    build_publishing_agent_registry,
)
from backend.orchestration.stage_runner import (
    StageRunResult,
)
from backend.publishing.enums import (
    ProductionStageType,
)
from backend.publishing.production_schemas import (
    CreateProductionRunRequest,
    ProductionStageDefinition,
)
from backend.services.agent_task_service import (
    AgentTaskService,
)
from backend.services.production_service import (
    ProductionService,
)
from backend.storage.model_utils import (
    json_dumps,
    json_loads,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


@dataclass
class HandoffCall:
    source_stage_id: str
    target_stage_id: str


class FakeHandoffManager:
    """Handoff 호출 순서를 검증하기 위한 Fake입니다."""

    def __init__(self) -> None:
        self.calls: list[HandoffCall] = []

    def handoff_stage_outputs(
        self,
        *,
        source_stage_id: str,
        target_stage_id: str,
        artifact_types: set[str] | None = None,
        replace: bool = False,
    ) -> list[str]:
        self.calls.append(
            HandoffCall(
                source_stage_id=source_stage_id,
                target_stage_id=target_stage_id,
            )
        )
        return []

    def attach_artifacts_to_task(
        self,
        *,
        stage_id: str,
        task_id: str,
    ) -> list[str]:
        return []


class FakeStageRunner:
    """Stage를 즉시 COMPLETED로 바꾸는 Fake Runner입니다."""

    def __init__(self, session: Session) -> None:
        self.repository = ProductionRepository(
            session
        )
        self.executed_stage_ids: list[str] = []

    async def run_stage(
        self,
        *,
        stage_id: str,
    ) -> StageRunResult:
        stage = self.repository.get_stage(stage_id)
        assert stage is not None

        self.executed_stage_ids.append(stage_id)

        artifact_id = f"artifact-{stage.stage_key}"

        stage.status = "COMPLETED"
        stage.output_artifact_ids_json = json_dumps(
            [artifact_id]
        )

        self.repository.save_stage(stage)

        tasks = self.repository.list_tasks_for_stage(
            stage.stage_id
        )
        assert tasks

        return StageRunResult(
            run_id=stage.run_id,
            stage_id=stage.stage_id,
            stage_key=stage.stage_key,
            stage_type=stage.stage_type,
            task_id=tasks[0].task_id,
            status="COMPLETED",
            success=True,
            output_artifact_ids=[artifact_id],
            agent_result=None,
        )


def build_plan_research_write_workflow(
    *,
    unit_id: str,
) -> list[ProductionStageDefinition]:
    """Engine 테스트용 3-Stage 최소 Workflow."""

    return [
        ProductionStageDefinition(
            stage_key="plan",
            stage_type=ProductionStageType.CHAPTER_PLANNING,
            order_index=10,
            unit_id=unit_id,
        ),
        ProductionStageDefinition(
            stage_key="research",
            stage_type=ProductionStageType.CHAPTER_RESEARCH,
            order_index=20,
            unit_id=unit_id,
            depends_on=["plan"],
        ),
        ProductionStageDefinition(
            stage_key="write",
            stage_type=ProductionStageType.CHAPTER_WRITING,
            order_index=30,
            unit_id=unit_id,
            depends_on=["plan", "research"],
        ),
    ]


def create_plan_research_write_run(
    session: Session,
    *,
    book_id: str,
    unit_id: str,
):
    return ProductionService(session).create_run(
        CreateProductionRunRequest(
            book_id=book_id,
            workspace_id="workspace-test",
            workflow_type="chapter",
        ),
        stages=build_plan_research_write_workflow(
            unit_id=unit_id
        ),
    )


def build_engine(*, session: Session):
    registry = build_publishing_agent_registry()

    fake_stage_runner = FakeStageRunner(session)
    fake_handoff_manager = FakeHandoffManager()

    task_service = AgentTaskService(
        session,
        registry,
    )

    engine = ProductionEngine(
        session=session,
        agent_registry=registry,
        stage_runner=fake_stage_runner,
        task_service=task_service,
        handoff_manager=fake_handoff_manager,
    )

    return engine, fake_stage_runner, fake_handoff_manager


@pytest.mark.anyio
async def test_execute_run_completes_all_stages(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine, runner, _handoff = build_engine(
        session=session
    )

    result = await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    assert result.success is True
    assert result.status == "COMPLETED"

    repository = ProductionRepository(session)

    run = repository.get_run(run_detail.run.run_id)

    assert run is not None
    assert run.status == "COMPLETED"
    assert run.current_stage_id is None
    assert run.completed_stages == 3
    assert run.failed_stages == 0

    stages = repository.list_stages(run.run_id)

    assert [
        stage.stage_key for stage in stages
    ] == [
        "plan",
        "research",
        "write",
    ]

    assert all(
        stage.status == "COMPLETED"
        for stage in stages
    )

    assert [
        repository.get_stage(stage_id).stage_key
        for stage_id in runner.executed_stage_ids
    ] == [
        "plan",
        "research",
        "write",
    ]


@pytest.mark.anyio
async def test_engine_creates_task_for_each_stage(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine, _, _ = build_engine(session=session)

    await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    repository = ProductionRepository(session)

    tasks = repository.list_tasks_for_run(
        run_detail.run.run_id
    )

    assert len(tasks) == 3

    assert [
        task.agent_role for task in tasks
    ] == [
        "PLANNER",
        "RESEARCHER",
        "WRITER",
    ]


@pytest.mark.anyio
async def test_engine_handoffs_all_dependencies(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine, _, handoff = build_engine(
        session=session
    )

    await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    repository = ProductionRepository(session)

    stages = repository.list_stages(
        run_detail.run.run_id
    )

    by_key = {
        stage.stage_key: stage
        for stage in stages
    }

    calls = {
        (
            call.source_stage_id,
            call.target_stage_id,
        )
        for call in handoff.calls
    }

    assert (
        by_key["plan"].stage_id,
        by_key["research"].stage_id,
    ) in calls

    assert (
        by_key["plan"].stage_id,
        by_key["write"].stage_id,
    ) in calls

    assert (
        by_key["research"].stage_id,
        by_key["write"].stage_id,
    ) in calls


@pytest.mark.anyio
async def test_unknown_run_raises(session):
    engine, _, _ = build_engine(session=session)

    with pytest.raises(ProductionRunNotFoundError):
        await engine.execute_run(
            run_id="missing-run"
        )


@pytest.mark.anyio
async def test_completed_run_cannot_execute_again(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine, _, _ = build_engine(session=session)

    await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    with pytest.raises(
        ProductionRunNotExecutableError
    ):
        await engine.execute_run(
            run_id=run_detail.run.run_id
        )


@pytest.mark.anyio
async def test_invalid_dependency_fails_run(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    repository = ProductionRepository(session)

    stages = repository.list_stages(
        run_detail.run.run_id
    )

    first_stage = stages[0]
    first_stage.depends_on_json = json_dumps(
        ["missing-stage"]
    )
    repository.save_stage(first_stage)

    engine, _, _ = build_engine(session=session)

    with pytest.raises(
        (
            ProductionWorkflowDeadlockError,
            ProductionStageDependencyError,
        )
    ):
        await engine.execute_run(
            run_id=run_detail.run.run_id
        )

    run = repository.get_run(run_detail.run.run_id)

    assert run is not None
    assert run.status == "FAILED"

    error = json_loads(run.error_json, {})
    assert error["message"]
