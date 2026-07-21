from __future__ import annotations

import pytest
from sqlmodel import Session

from backend.agents.context import (
    AgentContext,
    AgentContextBook,
    AgentContextRuntime,
    AgentContextUnit,
)
from backend.agents.registry import (
    AgentRegistry,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionStageType,
)
from backend.services.agent_task_service import (
    AgentTaskService,
)
from backend.storage.model_utils import (
    json_loads,
)
from backend.storage.models_publishing import (
    ProductionRun,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)
from tests.agents.fakes import (
    FakePlannerAgent,
)


@pytest.mark.anyio
async def test_execute_agent_task(
    isolated_session: Session,
    prepared_book,
    prepared_unit,
):
    registry = AgentRegistry()

    registry.register(
        FakePlannerAgent()
    )

    repository = ProductionRepository(
        isolated_session
    )

    run = repository.add_run(
        ProductionRun(
            book_id=prepared_book.book_id,
            workspace_id="workspace-test",
            total_stages=1,
        )
    )

    stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_key="unit-1:plan",
            stage_type=(
                ProductionStageType
                .CHAPTER_PLANNING
                .value
            ),
            order_index=10,
            status="READY",
        )
    )

    service = AgentTaskService(
        isolated_session,
        registry,
    )

    task = service.create_task(
        run_id=run.run_id,
        stage_id=stage.stage_id,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
        agent_role=(
            AgentRole.PLANNER.value
        ),
        agent_name="fake_planner",
        task_type="PLAN_CHAPTER",
    )

    context = AgentContext(
        runtime=AgentContextRuntime(
            run_id=run.run_id,
            stage_id=stage.stage_id,
            task_id=task.task_id,
            workspace_id="workspace-test",
            stage_key=stage.stage_key,
            stage_type=stage.stage_type,
            agent_role=task.agent_role,
            agent_name=task.agent_name,
            attempt=1,
        ),
        book=AgentContextBook(
            book_id=prepared_book.book_id,
            title=prepared_book.title,
        ),
        unit=AgentContextUnit(
            unit_id=prepared_unit.unit_id,
            title=prepared_unit.title,
            order_index=0,
        ),
    )

    result = await service.execute_task(
        task_id=task.task_id,
        context=context,
    )

    assert result.status.value == "SUCCESS"

    saved_task = repository.get_task(
        task.task_id
    )

    assert saved_task.status == "COMPLETED"

    output_artifact_ids = json_loads(
        saved_task.output_artifact_ids_json,
        [],
    )

    assert len(output_artifact_ids) == 1

    artifact = repository.get_artifact(
        output_artifact_ids[0]
    )

    assert artifact is not None

    assert (
        artifact.artifact_type
        == "CHAPTER_PLAN"
    )
