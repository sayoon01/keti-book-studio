from __future__ import annotations

import pytest
from sqlmodel import Session

from backend.agents.context_builder import (
    AgentContextBuilder,
)
from backend.agents.registry import AgentRegistry
from backend.orchestration.handoff_manager import (
    HandoffManager,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)
from backend.services.agent_task_service import (
    AgentTaskService,
)
from backend.storage.model_utils import (
    json_dumps,
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
    FakeProductionWriterAgent,
    FakeResearcherAgent,
)


@pytest.mark.anyio
async def test_plan_research_write_artifact_chain(
    isolated_session: Session,
    prepared_book,
    prepared_unit,
):
    registry = AgentRegistry()
    registry.register(FakePlannerAgent())
    registry.register(FakeResearcherAgent())
    registry.register(FakeProductionWriterAgent())

    repository = ProductionRepository(
        isolated_session
    )
    handoff = HandoffManager(isolated_session)
    task_service = AgentTaskService(
        isolated_session,
        registry,
    )
    context_builder = AgentContextBuilder(
        isolated_session
    )

    run = repository.add_run(
        ProductionRun(
            book_id=prepared_book.book_id,
            workspace_id="workspace-test",
            total_stages=3,
        )
    )

    plan_stage = repository.add_stage(
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

    research_stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_key="unit-1:research",
            stage_type=(
                ProductionStageType
                .CHAPTER_RESEARCH
                .value
            ),
            order_index=20,
            status="PENDING",
            depends_on_json=json_dumps(
                [plan_stage.stage_key]
            ),
        )
    )

    write_stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_key="unit-1:write",
            stage_type=(
                ProductionStageType
                .CHAPTER_WRITING
                .value
            ),
            order_index=30,
            status="PENDING",
            depends_on_json=json_dumps(
                [research_stage.stage_key]
            ),
        )
    )

    # 1) CHAPTER_PLANNING → CHAPTER_PLAN
    plan_task = task_service.create_task(
        run_id=run.run_id,
        stage_id=plan_stage.stage_id,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
        agent_role=AgentRole.PLANNER.value,
        agent_name="fake_planner",
        task_type="PLAN_CHAPTER",
    )

    plan_result = await task_service.execute_task(
        task_id=plan_task.task_id,
        context=context_builder.build_for_task(
            task_id=plan_task.task_id,
        ),
    )

    assert plan_result.status.value == "SUCCESS"
    assert plan_result.artifacts[0].artifact_type == (
        ProductionArtifactType.CHAPTER_PLAN.value
    )

    handoff.handoff_dependencies(
        target_stage_id=research_stage.stage_id,
    )

    # 2) CHAPTER_RESEARCH → RESEARCH_REPORT
    research_task = task_service.create_task(
        run_id=run.run_id,
        stage_id=research_stage.stage_id,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
        agent_role=AgentRole.RESEARCHER.value,
        agent_name="fake_researcher",
        task_type="RESEARCH_CHAPTER",
    )

    handoff.attach_artifacts_to_task(
        stage_id=research_stage.stage_id,
        task_id=research_task.task_id,
    )

    research_context = (
        context_builder.build_for_task(
            task_id=research_task.task_id,
        )
    )

    assert research_context.has_artifact(
        ProductionArtifactType.CHAPTER_PLAN
    )

    research_result = await task_service.execute_task(
        task_id=research_task.task_id,
        context=research_context,
    )

    assert research_result.status.value == "SUCCESS"
    assert (
        research_result.artifacts[0].artifact_type
        == ProductionArtifactType.RESEARCH_REPORT.value
    )

    # Writer는 plan + research 둘 다 필요하므로
    # plan 출력과 research 출력을 write stage로 전달
    handoff.handoff_stage_outputs(
        source_stage_id=plan_stage.stage_id,
        target_stage_id=write_stage.stage_id,
    )
    handoff.handoff_stage_outputs(
        source_stage_id=research_stage.stage_id,
        target_stage_id=write_stage.stage_id,
    )

    # 3) CHAPTER_WRITING → CHAPTER_DRAFT
    write_task = task_service.create_task(
        run_id=run.run_id,
        stage_id=write_stage.stage_id,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
        agent_role=AgentRole.WRITER.value,
        agent_name="fake_production_writer",
        task_type="WRITE_CHAPTER",
    )

    handoff.attach_artifacts_to_task(
        stage_id=write_stage.stage_id,
        task_id=write_task.task_id,
    )

    write_context = context_builder.build_for_task(
        task_id=write_task.task_id,
    )

    assert write_context.has_artifact(
        ProductionArtifactType.CHAPTER_PLAN
    )
    assert write_context.has_artifact(
        ProductionArtifactType.RESEARCH_REPORT
    )

    write_result = await task_service.execute_task(
        task_id=write_task.task_id,
        context=write_context,
    )

    assert write_result.status.value == "SUCCESS"
    assert (
        write_result.artifacts[0].artifact_type
        == ProductionArtifactType.CHAPTER_DRAFT.value
    )

    saved_write_task = repository.get_task(
        write_task.task_id
    )
    output_ids = json_loads(
        saved_write_task.output_artifact_ids_json,
        [],
    )
    assert len(output_ids) == 1

    draft = repository.get_artifact(output_ids[0])
    assert draft is not None
    assert (
        draft.artifact_type
        == ProductionArtifactType.CHAPTER_DRAFT.value
    )
