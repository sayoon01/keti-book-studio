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


class ReviserStage:
    """
    REVIEW_ARTIFACT의 수정 지침을 반영하여
    CHAPTER_DRAFT 새 버전을 생성하는 Stage.
    """

    name = "reviser"
    stage_name = "reviser"
    artifact_type = "CHAPTER_DRAFT"

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

        research_artifact = (
            _resolve_research_artifact(
                context
            )
        )

        chapter_draft = _resolve_chapter_draft(
            context
        )

        review_artifact = _resolve_review_artifact(
            context
        )

        previous_chapters = _get_context_value(
            context,
            "previous_chapters",
            [],
        )

        revision_number = _resolve_revision_number(
            context
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "ReviserStage book_config는 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "ReviserStage chapter_plan은 "
                "dictionary여야 합니다."
            )

        if not isinstance(
            research_artifact,
            dict,
        ):
            raise TypeError(
                "ReviserStage에는 "
                "research_artifact가 필요합니다."
            )

        if not isinstance(chapter_draft, dict):
            raise TypeError(
                "ReviserStage에는 "
                "chapter_draft가 필요합니다."
            )

        if not isinstance(review_artifact, dict):
            raise TypeError(
                "ReviserStage에는 "
                "review_artifact가 필요합니다."
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
            "ReviserStage started: "
            "chapter_id=%s revision=%s "
            "review_score=%s verdict=%s",
            chapter_id,
            revision_number,
            review_artifact.get("overall_score"),
            review_artifact.get("verdict"),
        )

        revised_draft = (
            await self._generation_service.revise_chapter(
                book_config=book_config,
                chapter_plan=chapter_plan,
                research_artifact=research_artifact,
                chapter_draft=chapter_draft,
                review_artifact=review_artifact,
                previous_chapters=previous_chapters,
                revision_number=revision_number,
            )
        )

        logger.info(
            "ReviserStage completed: "
            "chapter_id=%s revision=%s "
            "markdown_length=%s",
            revised_draft.get("chapter_id"),
            revised_draft.get(
                "metadata",
                {},
            ).get("revision"),
            len(
                str(
                    revised_draft.get(
                        "markdown",
                        "",
                    )
                )
            ),
        )

        return _merge_result_into_context(
            context=context,
            revised_draft=revised_draft,
        )

    async def run(
        self,
        context: Any,
    ) -> dict[str, Any]:
        """
        구 StageRunner 호환.
        """

        return await self.execute(context)


class ReviserAgent(BasePublishingAgent):
    """
    ProductionEngine용 Reviser Stage Handler.
    """

    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.REVISER.value,
            name="chapter_reviser",
            supported_stage_types={
                ProductionStageType.CHAPTER_REVISION.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
                ProductionArtifactType.CHAPTER_PLAN.value,
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.REVISED_CHAPTER.value,
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
        review_artifact = context.require_artifact(
            ProductionArtifactType.AGGREGATED_REVIEW_REPORT
        )
        plan_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        research_artifact = context.require_artifact(
            ProductionArtifactType.RESEARCH_REPORT
        )

        draft = parse_artifact_content(draft_artifact)
        review = parse_artifact_content(review_artifact)
        plan = parse_artifact_content(plan_artifact)
        research = parse_artifact_content(research_artifact)

        if not draft.get("artifact_type"):
            draft = {
                **draft,
                "artifact_type": "CHAPTER_DRAFT",
            }

        if not review.get("artifact_type"):
            review = {
                **review,
                "artifact_type": "REVIEW_ARTIFACT",
            }

        if not research.get("artifact_type"):
            research = {
                **research,
                "artifact_type": "RESEARCH_ARTIFACT",
            }

        payload = await self.llm_service.revise_chapter(
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
            review_artifact=review,
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_review"] = review_artifact.artifact_id

        return AgentResult.success(
            summary="챕터 수정본을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .REVISED_CHAPTER
                        .value
                    ),
                    name=f"{payload['title']} 수정본",
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
    # Reviser 재실행 시 가장 최근 수정본을 우선 사용한다.
    value = _get_context_value(
        context,
        "revised_draft",
        None,
    )

    if value is not None:
        return value

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
            artifacts.get("revised_draft")
            or artifacts.get("chapter_draft")
            or artifacts.get("draft")
            or artifacts.get("writer")
        )

    return None


def _resolve_review_artifact(
    context: Any,
) -> Any:
    value = _get_context_value(
        context,
        "review_artifact",
        None,
    )

    if value is not None:
        return value

    value = _get_context_value(
        context,
        "review",
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
        return artifacts.get("review")

    return None


def _resolve_revision_number(
    context: Any,
) -> int:
    explicit_revision = _get_context_value(
        context,
        "revision_number",
        None,
    )

    if (
        isinstance(explicit_revision, int)
        and not isinstance(explicit_revision, bool)
        and explicit_revision > 0
    ):
        return explicit_revision

    current_draft = _resolve_chapter_draft(
        context
    )

    if isinstance(current_draft, dict):
        metadata = current_draft.get(
            "metadata",
            {},
        )

        if isinstance(metadata, dict):
            current_revision = metadata.get(
                "revision"
            )

            if (
                isinstance(current_revision, int)
                and not isinstance(
                    current_revision,
                    bool,
                )
                and current_revision > 0
            ):
                return current_revision + 1

    return 1


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
    revised_draft: dict[str, Any],
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
                _resolve_research_artifact(
                    context
                )
            ),
            "chapter_draft": (
                _resolve_chapter_draft(
                    context
                )
            ),
            "review_artifact": (
                _resolve_review_artifact(
                    context
                )
            ),
            "previous_chapters": (
                _get_context_value(
                    context,
                    "previous_chapters",
                    [],
                )
            ),
        }

    # 기존 Writer Draft를 보존한다.
    if "original_draft" not in result:
        original_draft = result.get(
            "chapter_draft"
        )

        if isinstance(original_draft, dict):
            result["original_draft"] = (
                original_draft
            )

    result["revised_draft"] = revised_draft

    # 이후 Editor와 Reader는 chapter_draft 하나만 읽어도
    # 최신 버전을 받도록 현재 Draft도 갱신한다.
    result["chapter_draft"] = revised_draft
    result["draft"] = revised_draft

    artifacts = result.get("artifacts")

    if not isinstance(artifacts, dict):
        artifacts = {}

    artifacts = dict(artifacts)
    artifacts["revised_draft"] = revised_draft
    artifacts["chapter_draft"] = revised_draft
    artifacts["reviser"] = revised_draft

    result["artifacts"] = artifacts
    result["current_artifact"] = revised_draft
    result["last_stage"] = "reviser"

    return result
