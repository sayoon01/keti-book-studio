from __future__ import annotations

from sqlmodel import Session

from backend.agents.schemas import (
    AgentArtifact,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
)
from backend.services.artifact_service import (
    ArtifactService,
)
from backend.storage.model_utils import (
    json_loads,
)
from backend.storage.models_publishing import (
    AgentTask,
    ProductionRun,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


def test_create_artifact_and_link_outputs(
    isolated_session: Session,
    prepared_book,
    prepared_unit,
):
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
            stage_type="CHAPTER_PLANNING",
            order_index=10,
            status="READY",
        )
    )

    task = repository.add_task(
        AgentTask(
            run_id=run.run_id,
            stage_id=stage.stage_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            agent_role=(
                AgentRole.PLANNER.value
            ),
            agent_name="fake_planner",
            task_type="PLAN_CHAPTER",
            status="RUNNING",
        )
    )

    service = ArtifactService(
        isolated_session
    )

    record = service.create_artifact(
        run_id=run.run_id,
        stage_id=stage.stage_id,
        task_id=task.task_id,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
        created_by_role=(
            AgentRole.PLANNER.value
        ),
        artifact=AgentArtifact(
            artifact_type=(
                ProductionArtifactType
                .CHAPTER_PLAN
                .value
            ),
            name="테스트 계획",
            content={
                "sections": [
                    "개요",
                    "상세 설명",
                ]
            },
        ),
    )

    assert record.artifact_id.startswith(
        "artifact-"
    )

    assert record.version == 1

    saved_stage = repository.get_stage(
        stage.stage_id
    )

    saved_task = repository.get_task(
        task.task_id
    )

    assert record.artifact_id in json_loads(
        saved_stage.output_artifact_ids_json,
        [],
    )

    assert record.artifact_id in json_loads(
        saved_task.output_artifact_ids_json,
        [],
    )

    context_artifact = (
        service.get_context_artifact(
            record.artifact_id
        )
    )

    assert (
        context_artifact.artifact_type
        == "CHAPTER_PLAN"
    )

    assert context_artifact.content[
        "sections"
    ] == [
        "개요",
        "상세 설명",
    ]
