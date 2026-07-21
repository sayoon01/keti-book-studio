from __future__ import annotations

from sqlmodel import Session

from backend.storage.models_publishing import (
    ProductionRun,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


def test_create_production_run_and_stage(
    isolated_session: Session,
    prepared_book,
):
    book = prepared_book

    repository = ProductionRepository(
        isolated_session
    )

    run = repository.add_run(
        ProductionRun(
            book_id=book.book_id,
            workspace_id="workspace-test",
            workflow_type="technical_book",
            automation_level="BALANCED",
            total_stages=1,
        )
    )

    assert run.run_id.startswith("run-")
    assert run.status == "PENDING"

    stage = repository.add_stage(
        ProductionStage(
            run_id=run.run_id,
            book_id=book.book_id,
            stage_key="chapter-1:write",
            stage_type="CHAPTER_WRITING",
            order_index=10,
            status="READY",
        )
    )

    assert stage.stage_id.startswith("stage-")
    assert stage.run_id == run.run_id

    stages = repository.list_stages(run.run_id)

    assert len(stages) == 1
    assert stages[0].stage_key == "chapter-1:write"
