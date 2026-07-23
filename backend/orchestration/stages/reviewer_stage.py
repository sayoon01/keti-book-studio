from __future__ import annotations

import logging
from typing import Any

from backend.generation import (
    ChapterGenerationService,
)
from backend.orchestration.agent_schemas import (
    AgentArtifact,
    AgentResult,
)
from backend.orchestration.artifact_content import (
    parse_artifact_content,
)
from backend.orchestration.context import AgentContext
from backend.orchestration.stages.base import BasePublishingAgent
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


logger = logging.getLogger(__name__)


class ReviewerStage:
    """
    Chapter Draft를 검토하는 Stage.

    직접 LLM을 호출하지 않고
    ChapterGenerationService에 위임한다.
    """

    name = "reviewer"
    stage_name = "reviewer"
    artifact_type = "REVIEW_ARTIFACT"

    def __init__(
        self,
        *,
        generation_service: ChapterGenerationService | None = None,
    ) -> None:
        self._generation_service = (
            generation_service
            or ChapterGenerationService()
        )

    async def execute(
        self,
        context: Any,
    ) -> dict[str, Any]:
        book_config = _get_context_value(
            context,
            "book_config",
            {},
        )

        chapter_plan = _get_context_value(
            context,
            "chapter_plan",
            None,
        )

        if chapter_plan is None:
            chapter_plan = _get_context_value(
                context,
                "unit_plan",
                {},
            )

        research_artifact = _resolve_research_artifact(
            context
        )

        chapter_draft = _resolve_chapter_draft(
            context
        )

        previous_chapters = _get_context_value(
            context,
            "previous_chapters",
            [],
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "ReviewerStage book_config는 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "ReviewerStage chapter_plan은 "
                "dictionary여야 합니다."
            )

        if not isinstance(research_artifact, dict):
            raise TypeError(
                "ReviewerStage에는 research_artifact가 필요합니다."
            )

        if not isinstance(chapter_draft, dict):
            raise TypeError(
                "ReviewerStage에는 chapter_draft가 필요합니다."
            )

        if not isinstance(previous_chapters, list):
            previous_chapters = []

        chapter_id = (
            chapter_draft.get("chapter_id")
            or chapter_plan.get("chapter_id")
            or chapter_plan.get("unit_id")
            or chapter_plan.get("id")
        )

        logger.info(
            "ReviewerStage started: chapter_id=%s",
            chapter_id,
        )

        review_artifact = (
            await self._generation_service.review_chapter(
                book_config=book_config,
                chapter_plan=chapter_plan,
                research_artifact=research_artifact,
                chapter_draft=chapter_draft,
                previous_chapters=previous_chapters,
            )
        )

        logger.info(
            "ReviewerStage completed: "
            "chapter_id=%s score=%s verdict=%s issues=%s",
            review_artifact.get("chapter_id"),
            review_artifact.get("overall_score"),
            review_artifact.get("verdict"),
            len(review_artifact.get("issues", [])),
        )

        return _merge_result_into_context(
            context=context,
            review_artifact=review_artifact,
        )

    async def run(
        self,
        context: Any,
    ) -> dict[str, Any]:
        """
        구 StageRunner가 run()을 호출할 경우를 위한 임시 호환.
        """

        return await self.execute(context)


class ReviewerAgent(BasePublishingAgent):
    """
    ProductionEngine용 Reviewer Stage Handler.
    """

    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.REVIEW_AGGREGATOR.value,
            name="chapter_reviewer",
            supported_stage_types={
                ProductionStageType.CHAPTER_REVIEW.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.CHAPTER_PLAN.value,
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
            },
        )
        self.llm_service = (
            llm_service or ChapterGenerationService()
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        draft_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_DRAFT
        )
        plan_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        research_artifact = context.require_artifact(
            ProductionArtifactType.RESEARCH_REPORT
        )

        plan = parse_artifact_content(plan_artifact)
        research = parse_artifact_content(research_artifact)
        draft = parse_artifact_content(draft_artifact)

        # Production Artifact에 artifact_type이 없을 수 있어 보정한다.
        if not research.get("artifact_type"):
            research = {
                **research,
                "artifact_type": "RESEARCH_ARTIFACT",
            }

        if not draft.get("artifact_type"):
            draft = {
                **draft,
                "artifact_type": "CHAPTER_DRAFT",
            }

        payload = await self.llm_service.review_chapter(
            book_config={
                "title": context.book.title,
                "description": context.book.description,
                "target_reader": context.book.target_reader,
                "goal": context.book.purpose,
                "language": context.book.language,
            },
            chapter_plan=plan,
            research_artifact=research,
            chapter_draft=draft,
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_plan"] = plan_artifact.artifact_id
        payload["based_on_research"] = (
            research_artifact.artifact_id
        )

        return AgentResult.success(
            summary="챕터 초안 품질 검토를 완료했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .AGGREGATED_REVIEW_REPORT
                        .value
                    ),
                    name=f"{payload['title']} 검토 보고서",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
        )


def _resolve_research_artifact(
    context: Any,
) -> Any:
    value = _get_context_value(
        context,
        "research_artifact",
        None,
    )

    if value is not None:
        return value

    value = _get_context_value(
        context,
        "research",
        None,
    )

    if value is not None:
        return value

    artifacts = _get_context_value(
        context,
        "artifacts",
        {},
    )

    if isinstance(artifacts, dict):
        return artifacts.get("research")

    return None


def _resolve_chapter_draft(
    context: Any,
) -> Any:
    value = _get_context_value(
        context,
        "chapter_draft",
        None,
    )

    if value is not None:
        return value

    value = _get_context_value(
        context,
        "draft",
        None,
    )

    if value is not None:
        return value

    artifacts = _get_context_value(
        context,
        "artifacts",
        {},
    )

    if isinstance(artifacts, dict):
        return (
            artifacts.get("chapter_draft")
            or artifacts.get("draft")
            or artifacts.get("writer")
        )

    return None


def _get_context_value(
    context: Any,
    key: str,
    fallback: Any,
) -> Any:
    if isinstance(context, dict):
        return context.get(key, fallback)

    return getattr(context, key, fallback)


def _merge_result_into_context(
    *,
    context: Any,
    review_artifact: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(context, dict):
        result = dict(context)
    else:
        result = {
            "book_config": _get_context_value(
                context,
                "book_config",
                {},
            ),
            "chapter_plan": _get_context_value(
                context,
                "chapter_plan",
                _get_context_value(
                    context,
                    "unit_plan",
                    {},
                ),
            ),
            "research_artifact": (
                _resolve_research_artifact(context)
            ),
            "chapter_draft": (
                _resolve_chapter_draft(context)
            ),
            "previous_chapters": _get_context_value(
                context,
                "previous_chapters",
                [],
            ),
        }

    result["review"] = review_artifact
    result["review_artifact"] = review_artifact

    artifacts = result.get("artifacts")

    if not isinstance(artifacts, dict):
        artifacts = {}

    artifacts = dict(artifacts)
    artifacts["review"] = review_artifact

    result["artifacts"] = artifacts
    result["current_artifact"] = review_artifact
    result["last_stage"] = "reviewer"

    return result
