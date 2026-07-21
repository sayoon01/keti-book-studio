from __future__ import annotations

from sqlmodel import Session

from backend.agents.schemas import (
    AgentArtifact,
)
from backend.orchestration.handoff_manager import (
    HandoffManager,
)
from backend.services.artifact_service import (
    ArtifactService,
)
from backend.storage.model_utils import (
    json_dumps,
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


def test_handoff_stage_artifacts(
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
            total_stages=2,
        )
    )

    plan_stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_key="unit-1:plan",
            stage_type="CHAPTER_PLANNING",
            order_index=10,
            status="COMPLETED",
        )
    )

    write_stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_key="unit-1:write",
            stage_type="CHAPTER_WRITING",
            order_index=20,
            status="PENDING",
            depends_on_json=json_dumps(
                [
                    plan_stage.stage_key,
                ]
            ),
        )
    )

    artifact_service = ArtifactService(
        isolated_session
    )

    plan_artifact = (
        artifact_service.create_artifact(
            run_id=run.run_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            stage_id=plan_stage.stage_id,
            created_by_role="PLANNER",
            artifact=AgentArtifact(
                artifact_type="CHAPTER_PLAN",
                name="챕터 계획",
                content={
                    "sections": [
                        "개요",
                        "본문",
                    ]
                },
            ),
        )
    )

    manager = HandoffManager(
        isolated_session
    )

    artifact_ids = (
        manager.handoff_dependencies(
            target_stage_id=(
                write_stage.stage_id
            )
        )
    )

    assert artifact_ids == [
        plan_artifact.artifact_id
    ]

    saved_write_stage = (
        repository.get_stage(
            write_stage.stage_id
        )
    )

    assert json_loads(
        saved_write_stage
        .input_artifact_ids_json,
        [],
    ) == [
        plan_artifact.artifact_id
    ]

    writer_task = repository.add_task(
        AgentTask(
            run_id=run.run_id,
            stage_id=write_stage.stage_id,
            book_id=prepared_book.book_id,
            unit_id=prepared_unit.unit_id,
            agent_role="WRITER",
            agent_name="fake_writer",
            task_type="WRITE_CHAPTER",
            status="READY",
        )
    )

    task_artifact_ids = (
        manager.attach_artifacts_to_task(
            stage_id=write_stage.stage_id,
            task_id=writer_task.task_id,
        )
    )

    assert task_artifact_ids == [
        plan_artifact.artifact_id
    ]
