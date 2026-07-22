from __future__ import annotations

import pytest

from backend.publishing.enums import (
    PublishingEventType,
)
from backend.services.event_service import (
    EventNotFoundError,
    EventService,
)
from backend.storage.model_utils import (
    json_loads,
)


def test_event_service_publishes_event(
    session,
):
    service = EventService(
        session
    )

    event = service.publish(
        event_type=(
            PublishingEventType
            .RUN_STARTED
        ),
        run_id="run-test",
        book_id="book-test",
        title="Run 시작",
        message="테스트 Run 시작",
        payload={
            "workflow_type": (
                "chapter"
            ),
        },
    )

    assert event.event_id
    assert event.event_type == (
        PublishingEventType
        .RUN_STARTED
        .value
    )

    assert event.run_id == "run-test"
    assert event.book_id == "book-test"
    assert event.title == "Run 시작"
    assert event.severity == "INFO"

    payload = json_loads(
        event.payload_json,
        {},
    )

    assert payload == {
        "workflow_type": "chapter",
    }


def test_event_service_accepts_string_type(
    session,
):
    service = EventService(
        session
    )

    event = service.publish(
        event_type="STAGE_STARTED",
        title="Stage 시작",
        stage_id="stage-test",
    )

    assert (
        event.event_type
        == "STAGE_STARTED"
    )


def test_list_events_for_run_is_chronological(
    session,
):
    service = EventService(
        session
    )

    first = service.publish(
        event_type="RUN_STARTED",
        run_id="run-order",
        title="첫 번째",
    )

    second = service.publish(
        event_type="STAGE_STARTED",
        run_id="run-order",
        stage_id="stage-order",
        title="두 번째",
    )

    third = service.publish(
        event_type="STAGE_COMPLETED",
        run_id="run-order",
        stage_id="stage-order",
        title="세 번째",
    )

    events = service.list_events_for_run(
        "run-order"
    )

    assert [
        event.event_id
        for event in events
    ] == [
        first.event_id,
        second.event_id,
        third.event_id,
    ]


def test_list_events_for_stage(
    session,
):
    service = EventService(
        session
    )

    service.publish(
        event_type="STAGE_STARTED",
        run_id="run-stage",
        stage_id="stage-target",
        title="대상 Stage",
    )

    service.publish(
        event_type="STAGE_STARTED",
        run_id="run-stage",
        stage_id="stage-other",
        title="다른 Stage",
    )

    events = (
        service.list_events_for_stage(
            "stage-target"
        )
    )

    assert len(events) == 1
    assert (
        events[0].stage_id
        == "stage-target"
    )


def test_list_recent_events_newest_first(
    session,
):
    service = EventService(
        session
    )

    first = service.publish(
        event_type="RUN_STARTED",
        run_id="run-recent",
        title="첫 번째",
    )

    second = service.publish(
        event_type="RUN_COMPLETED",
        run_id="run-recent",
        title="두 번째",
    )

    events = service.list_recent_events(
        run_id="run-recent",
        limit=10,
    )

    assert [
        event.event_id
        for event in events
    ] == [
        second.event_id,
        first.event_id,
    ]


def test_require_event_raises_when_missing(
    session,
):
    service = EventService(
        session
    )

    with pytest.raises(
        EventNotFoundError
    ):
        service.require_event(
            "missing-event"
        )
