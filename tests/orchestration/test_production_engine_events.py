from __future__ import annotations

import pytest

from backend.agents.registry import AgentRegistry
from backend.orchestration.production_engine import (
    ProductionEngine,
)
from backend.publishing.enums import (
    ProductionStageType,
    PublishingEventType,
)
from backend.publishing.production_schemas import (
    CreateProductionRunRequest,
    ProductionStageDefinition,
)
from backend.services.event_service import (
    EventService,
)
from backend.services.production_service import (
    ProductionService,
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


def create_plan_research_write_run(
    session,
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


@pytest.mark.anyio
async def test_engine_publishes_run_and_stage_events(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine = ProductionEngine(
        session=session,
        agent_registry=build_fake_publishing_registry(),
    )

    result = await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    assert result.success is True

    events = EventService(session).list_events_for_run(
        run_detail.run.run_id
    )

    event_types = [
        event.event_type for event in events
    ]

    assert (
        PublishingEventType.RUN_STARTED.value
        in event_types
    )

    assert (
        PublishingEventType.RUN_COMPLETED.value
        in event_types
    )

    assert event_types.count(
        PublishingEventType.STAGE_STARTED.value
    ) == 3

    assert event_types.count(
        PublishingEventType.STAGE_COMPLETED.value
    ) == 3

    assert (
        PublishingEventType.RUN_FAILED.value
        not in event_types
    )

    assert (
        PublishingEventType.STAGE_FAILED.value
        not in event_types
    )


@pytest.mark.anyio
async def test_engine_event_order(
    session,
    prepared_book,
    prepared_unit,
):
    run_detail = create_plan_research_write_run(
        session,
        book_id=prepared_book.book_id,
        unit_id=prepared_unit.unit_id,
    )

    engine = ProductionEngine(
        session=session,
        agent_registry=build_fake_publishing_registry(),
    )

    await engine.execute_run(
        run_id=run_detail.run.run_id
    )

    events = EventService(session).list_events_for_run(
        run_detail.run.run_id
    )

    engine_event_types = [
        event.event_type
        for event in events
        if event.actor_id == "production_engine"
    ]

    assert engine_event_types[0] == (
        PublishingEventType.RUN_STARTED.value
    )

    assert engine_event_types[-1] == (
        PublishingEventType.RUN_COMPLETED.value
    )

    assert engine_event_types == [
        PublishingEventType.RUN_STARTED.value,
        PublishingEventType.STAGE_STARTED.value,
        PublishingEventType.STAGE_COMPLETED.value,
        PublishingEventType.STAGE_STARTED.value,
        PublishingEventType.STAGE_COMPLETED.value,
        PublishingEventType.STAGE_STARTED.value,
        PublishingEventType.STAGE_COMPLETED.value,
        PublishingEventType.RUN_COMPLETED.value,
    ]
