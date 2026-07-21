from __future__ import annotations

from sqlmodel import Session, select

from backend.publishing.production_schemas import (
    CreateProductionRunRequest,
)
from backend.publishing.workflows import (
    build_chapter_workflow,
)
from backend.services.production_service import (
    ProductionService,
)
from backend.storage.models_publishing import (
    PublishingEvent,
)


def test_create_chapter_production_run(
    isolated_session: Session,
    prepared_book,
    prepared_unit,
):
    service = ProductionService(
        isolated_session
    )

    result = service.create_run(
        CreateProductionRunRequest(
            book_id=prepared_book.book_id,
            workspace_id="workspace-test",
            workflow_type="technical_book",
            automation_level="BALANCED",
            input_data={
                "requested_action": (
                    "generate_chapter"
                )
            },
        ),
        stages=build_chapter_workflow(
            unit_id=prepared_unit.unit_id,
        ),
    )

    assert result.run.status == "PENDING"
    assert result.run.total_stages == 8

    assert len(result.stages) == 8

    assert result.stages[0].status == "READY"
    assert result.stages[1].status == "PENDING"

    assert (
        result.stages[0].stage_type
        == "CHAPTER_PLANNING"
    )

    events = list(
        isolated_session.exec(
            select(PublishingEvent).where(
                PublishingEvent.run_id
                == result.run.run_id
            )
        ).all()
    )

    # RUN_CREATED 1개 + STAGE_CREATED 8개
    assert len(events) == 9
