from __future__ import annotations

from backend.events.event_publisher import (
    EventPublisher,
)
from backend.publishing.enums import (
    PublishingEventType,
)
from backend.services.event_service import (
    EventService,
)
from backend.storage.model_utils import (
    json_dumps,
    json_loads,
)
from backend.storage.models_publishing import (
    ProductionRun,
    ProductionStage,
)


def make_run() -> ProductionRun:
    return ProductionRun(
        run_id="run-publisher",
        book_id="book-publisher",
        workspace_id="workspace-publisher",
        workflow_type="chapter",
        automation_level="BALANCED",
        status="RUNNING",
        total_stages=3,
        completed_stages=0,
        failed_stages=0,
    )


def make_stage() -> ProductionStage:
    return ProductionStage(
        stage_id="stage-publisher",
        run_id="run-publisher",
        book_id="book-publisher",
        unit_id=None,
        stage_key="plan",
        stage_type="CHAPTER_PLANNING",
        order_index=0,
        status="RUNNING",
        depends_on_json="[]",
    )


def test_publish_run_started(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    event = publisher.run_started(
        make_run()
    )

    assert event.event_type == (
        PublishingEventType
        .RUN_STARTED
        .value
    )

    assert event.run_id == (
        "run-publisher"
    )

    assert event.actor_id == (
        "production_engine"
    )

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload["total_stages"] == 3


def test_publish_stage_started(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    event = publisher.stage_started(
        make_stage()
    )

    assert event.event_type == (
        PublishingEventType
        .STAGE_STARTED
        .value
    )

    assert event.stage_id == (
        "stage-publisher"
    )

    assert event.title == (
        "챕터 계획 시작"
    )


def test_publish_stage_completed(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    stage = make_stage()

    stage.status = "COMPLETED"
    stage.output_artifact_ids_json = (
        json_dumps(
            [
                "artifact-plan",
            ]
        )
    )

    event = publisher.stage_completed(
        stage
    )

    assert event.event_type == (
        PublishingEventType
        .STAGE_COMPLETED
        .value
    )

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload[
        "output_artifact_ids"
    ] == [
        "artifact-plan",
    ]


def test_publish_run_completed(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    run = make_run()

    run.status = "COMPLETED"
    run.completed_stages = 3
    run.result_json = json_dumps(
        {
            "output_artifact_ids": [
                "artifact-plan",
                "artifact-research",
                "artifact-draft",
            ],
        }
    )

    event = publisher.run_completed(
        run
    )

    assert event.event_type == (
        PublishingEventType
        .RUN_COMPLETED
        .value
    )

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload[
        "completed_stages"
    ] == 3

    assert payload[
        "output_artifact_ids"
    ] == [
        "artifact-plan",
        "artifact-research",
        "artifact-draft",
    ]


def test_publish_stage_failed(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    stage = make_stage()
    stage.status = "FAILED"

    event = publisher.stage_failed(
        stage,
        error=RuntimeError(
            "Stage 테스트 실패"
        ),
    )

    assert event.event_type == (
        PublishingEventType
        .STAGE_FAILED
        .value
    )

    assert event.severity == "ERROR"

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload[
        "error_message"
    ] == "Stage 테스트 실패"


def test_publish_run_failed(
    session,
):
    publisher = EventPublisher(
        EventService(session)
    )

    run = make_run()
    run.status = "FAILED"
    run.failed_stages = 1

    event = publisher.run_failed(
        run,
        error=RuntimeError(
            "Run 테스트 실패"
        ),
    )

    assert event.event_type == (
        PublishingEventType
        .RUN_FAILED
        .value
    )

    assert event.severity == "ERROR"

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload[
        "error_message"
    ] == "Run 테스트 실패"
