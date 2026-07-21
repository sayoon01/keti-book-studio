from __future__ import annotations

from sqlmodel import Session, select

from backend.storage.models_publishing import (
    PublishingEvent,
)


class EventRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_event(
        self,
        event: PublishingEvent,
    ) -> PublishingEvent:
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def get_event(
        self,
        event_id: str,
    ) -> PublishingEvent | None:
        return self.session.get(
            PublishingEvent,
            event_id,
        )

    def list_events_for_run(
        self,
        run_id: str,
        *,
        limit: int = 500,
    ) -> list[PublishingEvent]:
        statement = (
            select(PublishingEvent)
            .where(PublishingEvent.run_id == run_id)
            .order_by(PublishingEvent.created_at)
            .limit(limit)
        )

        return list(self.session.exec(statement).all())

    def list_events_for_stage(
        self,
        stage_id: str,
    ) -> list[PublishingEvent]:
        statement = (
            select(PublishingEvent)
            .where(
                PublishingEvent.stage_id == stage_id
            )
            .order_by(PublishingEvent.created_at)
        )

        return list(self.session.exec(statement).all())

    def list_events_for_task(
        self,
        task_id: str,
    ) -> list[PublishingEvent]:
        statement = (
            select(PublishingEvent)
            .where(PublishingEvent.task_id == task_id)
            .order_by(PublishingEvent.created_at)
        )

        return list(self.session.exec(statement).all())
