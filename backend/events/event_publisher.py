from __future__ import annotations

from backend.publishing.enums import (
    PublishingEventType,
)
from backend.services.event_service import (
    EventService,
)
from backend.storage.model_utils import (
    json_loads,
)
from backend.storage.models_publishing import (
    ProductionRun,
    ProductionStage,
    PublishingEvent,
)


class EventPublisher:
    """
    ProductionEngine이 이벤트를 간단하게 발행할 수
    있도록 지원하는 Facade입니다.

    EventService.publish()의 반복적인 인자를
    Run/Stage 모델에서 자동으로 채웁니다.
    """

    def __init__(
        self,
        event_service: EventService,
    ) -> None:
        self.event_service = event_service

    # =====================================================
    # Run 이벤트
    # =====================================================

    def run_started(
        self,
        run: ProductionRun,
    ) -> PublishingEvent:
        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .RUN_STARTED
            ),
            run_id=run.run_id,
            book_id=run.book_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title="Production Run 시작",
            message=(
                "도서 제작 Production Run이 "
                "시작되었습니다."
            ),
            payload={
                "workflow_type": (
                    run.workflow_type
                ),
                "automation_level": (
                    run.automation_level
                ),
                "total_stages": (
                    run.total_stages
                ),
            },
            severity="INFO",
        )

    def run_completed(
        self,
        run: ProductionRun,
        *,
        output_artifact_ids: (
            list[str] | None
        ) = None,
    ) -> PublishingEvent:
        if output_artifact_ids is None:
            result_data = json_loads(
                run.result_json,
                {},
            )

            output_artifact_ids = list(
                result_data.get(
                    "output_artifact_ids",
                    [],
                )
            )

        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .RUN_COMPLETED
            ),
            run_id=run.run_id,
            book_id=run.book_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title="Production Run 완료",
            message=(
                "모든 제작 Stage가 정상적으로 "
                "완료되었습니다."
            ),
            payload={
                "completed_stages": (
                    run.completed_stages
                ),
                "failed_stages": (
                    run.failed_stages
                ),
                "output_artifact_ids": (
                    output_artifact_ids
                ),
            },
            severity="INFO",
        )

    def run_failed(
        self,
        run: ProductionRun,
        *,
        error: Exception | str,
    ) -> PublishingEvent:
        error_message = str(
            error
        )

        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .RUN_FAILED
            ),
            run_id=run.run_id,
            book_id=run.book_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title="Production Run 실패",
            message=error_message,
            payload={
                "error_type": (
                    type(error).__name__
                    if isinstance(
                        error,
                        Exception,
                    )
                    else "Error"
                ),
                "error_message": (
                    error_message
                ),
                "completed_stages": (
                    run.completed_stages
                ),
                "failed_stages": (
                    run.failed_stages
                ),
            },
            severity="ERROR",
        )

    # =====================================================
    # Stage 이벤트
    # =====================================================

    def stage_started(
        self,
        stage: ProductionStage,
    ) -> PublishingEvent:
        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .STAGE_STARTED
            ),
            run_id=stage.run_id,
            stage_id=stage.stage_id,
            book_id=stage.book_id,
            unit_id=stage.unit_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title=self._stage_title(
                stage=stage,
                action="시작",
            ),
            message=(
                f"{stage.stage_key} Stage가 "
                "시작되었습니다."
            ),
            payload={
                "stage_key": (
                    stage.stage_key
                ),
                "stage_type": (
                    stage.stage_type
                ),
                "order_index": (
                    stage.order_index
                ),
                "retry_count": (
                    stage.retry_count
                ),
            },
            severity="INFO",
        )

    def stage_completed(
        self,
        stage: ProductionStage,
        *,
        output_artifact_ids: (
            list[str] | None
        ) = None,
    ) -> PublishingEvent:
        if output_artifact_ids is None:
            output_artifact_ids = list(
                json_loads(
                    stage.output_artifact_ids_json,
                    [],
                )
            )

        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .STAGE_COMPLETED
            ),
            run_id=stage.run_id,
            stage_id=stage.stage_id,
            book_id=stage.book_id,
            unit_id=stage.unit_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title=self._stage_title(
                stage=stage,
                action="완료",
            ),
            message=(
                f"{stage.stage_key} Stage가 "
                "정상적으로 완료되었습니다."
            ),
            payload={
                "stage_key": (
                    stage.stage_key
                ),
                "stage_type": (
                    stage.stage_type
                ),
                "output_artifact_ids": (
                    output_artifact_ids
                ),
            },
            severity="INFO",
        )

    def stage_failed(
        self,
        stage: ProductionStage,
        *,
        error: Exception | str,
    ) -> PublishingEvent:
        error_message = str(
            error
        )

        return self.event_service.publish(
            event_type=(
                PublishingEventType
                .STAGE_FAILED
            ),
            run_id=stage.run_id,
            stage_id=stage.stage_id,
            book_id=stage.book_id,
            unit_id=stage.unit_id,
            actor_type="SYSTEM",
            actor_id="production_engine",
            title=self._stage_title(
                stage=stage,
                action="실패",
            ),
            message=error_message,
            payload={
                "stage_key": (
                    stage.stage_key
                ),
                "stage_type": (
                    stage.stage_type
                ),
                "error_type": (
                    type(error).__name__
                    if isinstance(
                        error,
                        Exception,
                    )
                    else "Error"
                ),
                "error_message": (
                    error_message
                ),
                "retry_count": (
                    stage.retry_count
                ),
                "max_retries": (
                    stage.max_retries
                ),
            },
            severity="ERROR",
        )

    @staticmethod
    def _stage_title(
        *,
        stage: ProductionStage,
        action: str,
    ) -> str:
        """
        Stage Type을 사용자 친화적인 이름으로 변환합니다.
        """

        labels: dict[str, str] = {
            "CHAPTER_PLANNING": (
                "챕터 계획"
            ),
            "CHAPTER_RESEARCH": (
                "자료 조사"
            ),
            "CHAPTER_WRITING": (
                "챕터 작성"
            ),
            "CHAPTER_REVIEW": (
                "챕터 검토"
            ),
            "CHAPTER_EDITING": (
                "편집 판단"
            ),
            "CHAPTER_REVISION": (
                "챕터 수정"
            ),
            "CHAPTER_READER_TEST": (
                "독자 테스트"
            ),
            "CHAPTER_FINALIZATION": (
                "최종 확정"
            ),
        }

        label = labels.get(
            stage.stage_type,
            stage.stage_key,
        )

        return f"{label} {action}"
