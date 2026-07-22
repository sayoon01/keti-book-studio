from __future__ import annotations

from enum import Enum
from typing import Any

from sqlmodel import Session, select

from backend.storage.model_utils import (
    json_dumps,
)
from backend.storage.models_publishing import (
    PublishingEvent,
)


class EventServiceError(RuntimeError):
    """
    PublishingEvent 저장 및 조회 중 발생하는 기본 예외입니다.
    """


class EventNotFoundError(EventServiceError):
    """
    요청한 이벤트를 찾을 수 없을 때 발생합니다.
    """


class EventService:
    """
    PublishingEvent 저장과 조회를 담당합니다.

    역할:

    1. 이벤트 타입 정규화
    2. payload JSON 직렬화
    3. PublishingEvent DB 저장
    4. Run / Stage / Task별 이벤트 조회
    5. 최근 이벤트 조회

    ProductionEngine이나 AgentTaskService는
    PublishingEvent 모델을 직접 만들지 않고
    가능하면 이 서비스를 사용합니다.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def publish(
        self,
        *,
        event_type: str | Enum,
        title: str,
        run_id: str | None = None,
        stage_id: str | None = None,
        task_id: str | None = None,
        book_id: str | None = None,
        unit_id: str | None = None,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        severity: str = "INFO",
    ) -> PublishingEvent:
        """
        PublishingEvent를 생성하고 DB에 저장합니다.
        """

        normalized_event_type = (
            self._normalize_enum_value(
                event_type
            )
        )

        normalized_actor_type = (
            str(actor_type)
            .strip()
            .upper()
        )

        normalized_severity = (
            str(severity)
            .strip()
            .upper()
        )

        event = PublishingEvent(
            run_id=run_id,
            stage_id=stage_id,
            task_id=task_id,
            book_id=book_id,
            unit_id=unit_id,
            event_type=normalized_event_type,
            actor_type=normalized_actor_type,
            actor_id=actor_id,
            title=title,
            message=message,
            payload_json=json_dumps(
                payload or {}
            ),
            severity=normalized_severity,
        )

        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)

        return event

    def get_event(
        self,
        event_id: str,
    ) -> PublishingEvent | None:
        """
        event_id로 이벤트 하나를 조회합니다.
        """

        return self.session.get(
            PublishingEvent,
            event_id,
        )

    def require_event(
        self,
        event_id: str,
    ) -> PublishingEvent:
        """
        event_id로 이벤트를 조회하며,
        없으면 EventNotFoundError를 발생시킵니다.
        """

        event = self.get_event(
            event_id
        )

        if event is None:
            raise EventNotFoundError(
                "PublishingEvent를 찾을 수 "
                f"없습니다: {event_id}"
            )

        return event

    def list_events_for_run(
        self,
        run_id: str,
        *,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[PublishingEvent]:
        """
        Run에 속한 이벤트를 조회합니다.

        기본은 오래된 이벤트부터 반환합니다.
        """

        statement = select(
            PublishingEvent
        ).where(
            PublishingEvent.run_id == run_id
        )

        if newest_first:
            statement = statement.order_by(
                PublishingEvent.created_at.desc(),
                PublishingEvent.event_id.desc(),
            )
        else:
            statement = statement.order_by(
                PublishingEvent.created_at.asc(),
                PublishingEvent.event_id.asc(),
            )

        if limit is not None:
            statement = statement.limit(
                max(limit, 0)
            )

        return list(
            self.session.exec(
                statement
            ).all()
        )

    def list_events_for_stage(
        self,
        stage_id: str,
        *,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[PublishingEvent]:
        """
        Stage에 속한 이벤트를 조회합니다.
        """

        statement = select(
            PublishingEvent
        ).where(
            PublishingEvent.stage_id
            == stage_id
        )

        if newest_first:
            statement = statement.order_by(
                PublishingEvent.created_at.desc(),
                PublishingEvent.event_id.desc(),
            )
        else:
            statement = statement.order_by(
                PublishingEvent.created_at.asc(),
                PublishingEvent.event_id.asc(),
            )

        if limit is not None:
            statement = statement.limit(
                max(limit, 0)
            )

        return list(
            self.session.exec(
                statement
            ).all()
        )

    def list_events_for_task(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[PublishingEvent]:
        """
        Task에 속한 이벤트를 조회합니다.
        """

        statement = select(
            PublishingEvent
        ).where(
            PublishingEvent.task_id == task_id
        )

        if newest_first:
            statement = statement.order_by(
                PublishingEvent.created_at.desc(),
                PublishingEvent.event_id.desc(),
            )
        else:
            statement = statement.order_by(
                PublishingEvent.created_at.asc(),
                PublishingEvent.event_id.asc(),
            )

        if limit is not None:
            statement = statement.limit(
                max(limit, 0)
            )

        return list(
            self.session.exec(
                statement
            ).all()
        )

    def list_recent_events(
        self,
        *,
        limit: int = 100,
        run_id: str | None = None,
        book_id: str | None = None,
        unit_id: str | None = None,
    ) -> list[PublishingEvent]:
        """
        최근 이벤트를 최신순으로 조회합니다.

        운영 화면의 Activity Feed에 사용할 수 있습니다.
        """

        statement = select(
            PublishingEvent
        )

        if run_id is not None:
            statement = statement.where(
                PublishingEvent.run_id == run_id
            )

        if book_id is not None:
            statement = statement.where(
                PublishingEvent.book_id == book_id
            )

        if unit_id is not None:
            statement = statement.where(
                PublishingEvent.unit_id == unit_id
            )

        statement = statement.order_by(
            PublishingEvent.created_at.desc(),
            PublishingEvent.event_id.desc(),
        ).limit(
            max(limit, 0)
        )

        return list(
            self.session.exec(
                statement
            ).all()
        )

    @staticmethod
    def _normalize_enum_value(
        value: str | Enum,
    ) -> str:
        """
        문자열과 Enum을 모두 문자열 값으로 변환합니다.

        예:

        PublishingEventType.RUN_STARTED
        → "RUN_STARTED"

        "RUN_STARTED"
        → "RUN_STARTED"
        """

        if isinstance(
            value,
            Enum,
        ):
            return str(
                value.value
            )

        return str(
            value
        ).strip()
