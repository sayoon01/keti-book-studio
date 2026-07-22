from __future__ import annotations

import pytest

from backend.orchestration.stages.registry import AgentRegistry
from backend.orchestration.production_engine import (
    ProductionEngine,
)
from backend.publishing.enums import (
    ProductionArtifactType,
    ProductionStageType,
)
from backend.publishing.production_schemas import (
    CreateProductionRunRequest,
    ProductionStageDefinition,
)
from backend.services.production_service import (
    ProductionService,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)
from tests.agents.fakes import (
    FakePlannerAgent,
    FakeProductionWriterAgent,
    FakeResearcherAgent,
)


def build_fake_publishing_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(FakePlannerAgent())
    registry.register(FakeResearcherAgent())
    registry.register(FakeProductionWriterAgent())
    return registry


def build_plan_research_write_workflow(
    *,
    unit_id: str,
) -> list[ProductionStageDefinition]:
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


@pytest.mark.anyio
async def test_engine_runs_plan_research_write(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = ProductionService(session).create_run(
        CreateProductionRunRequest(
            book_id=prepared_book.book_id,
            workspace_id="workspace-test",
            workflow_type="chapter",
        ),
        stages=build_plan_research_write_workflow(
            unit_id=prepared_unit.unit_id
        ),
    )

    engine = ProductionEngine(
        session=session,
        agent_registry=build_fake_publishing_registry(),
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
    assert run.completed_stages == 3

    stages = repository.list_stages(run.run_id)

    assert [stage.status for stage in stages] == [
        "COMPLETED",
        "COMPLETED",
        "COMPLETED",
    ]

    draft = repository.get_latest_artifact(
        run_id=run.run_id,
        unit_id=prepared_unit.unit_id,
        artifact_type=ProductionArtifactType.CHAPTER_DRAFT,
    )

    assert draft is not None
    assert draft.stage_id is not None
    assert draft.task_id is not None
