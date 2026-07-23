from __future__ import annotations

import logging
from typing import Any

from backend.generation.chapter_generation_service import (
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


class EditorStage:
    """
    사용자 편집 명령을 최신 CHAPTER_DRAFT에 적용한다.
    """

    name = "editor"
    stage_name = "editor"
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

        chapter_draft = _resolve_current_draft(
            context
        )

        editor_command = _get_context_value(
            context,
            "editor_command",
            None,
        )

        research_artifact = (
            _resolve_optional_artifact(
                context,
                direct_keys=(
                    "research_artifact",
                    "research",
                ),
                artifact_keys=(
                    "research",
                ),
            )
        )

        review_artifact = (
            _resolve_optional_artifact(
                context,
                direct_keys=(
                    "review_artifact",
                    "review",
                ),
                artifact_keys=(
                    "review",
                ),
            )
        )

        previous_chapters = _get_context_value(
            context,
            "previous_chapters",
            [],
        )

        revision_number = _get_context_value(
            context,
            "revision_number",
            None,
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "EditorStage book_config는 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "EditorStage chapter_plan은 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_draft, dict):
            raise TypeError(
                "EditorStage에는 현재 "
                "chapter_draft가 필요합니다."
            )

        if editor_command is None:
            raise ValueError(
                "EditorStage에는 editor_command가 "
                "필요합니다."
            )

        if not isinstance(previous_chapters, list):
            previous_chapters = []

        chapter_id = (
            chapter_draft.get("chapter_id")
            or chapter_plan.get("chapter_id")
            or chapter_plan.get("unit_id")
            or chapter_plan.get("id")
        )

        mode = (
            editor_command.get("mode")
            if isinstance(editor_command, dict)
            else getattr(
                editor_command,
                "mode",
                None,
            )
        )

        scope = (
            editor_command.get("scope")
            if isinstance(editor_command, dict)
            else getattr(
                editor_command,
                "scope",
                None,
            )
        )

        logger.info(
            "EditorStage started: "
            "chapter_id=%s mode=%s scope=%s",
            chapter_id,
            getattr(mode, "value", mode),
            getattr(scope, "value", scope),
        )

        edited_draft = (
            await self._generation_service.edit_chapter(
                book_config=book_config,
                chapter_plan=chapter_plan,
                chapter_draft=chapter_draft,
                editor_command=editor_command,
                research_artifact=research_artifact,
                review_artifact=review_artifact,
                previous_chapters=previous_chapters,
                revision_number=revision_number,
            )
        )

        metadata = edited_draft.get(
            "metadata",
            {},
        )

        logger.info(
            "EditorStage completed: "
            "chapter_id=%s revision=%s "
            "mode=%s scope=%s markdown_length=%s",
            edited_draft.get("chapter_id"),
            metadata.get("revision"),
            metadata.get("edit_mode"),
            metadata.get("edit_scope"),
            len(
                str(
                    edited_draft.get(
                        "markdown",
                        "",
                    )
                )
            ),
        )

        return _merge_result_into_context(
            context=context,
            previous_draft=chapter_draft,
            edited_draft=edited_draft,
        )

    async def run(
        self,
        context: Any,
    ) -> dict[str, Any]:
        return await self.execute(context)


class EditorAgent(BasePublishingAgent):
    """
    ProductionEngine용 Editor Stage Handler.

    현재는 사용자 명령 기반 EditorStage와 별도로,
    편집 지시서(EDITORIAL_DECISION) 생성 경로를 유지한다.
    """

    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.EDITOR.value,
            name="chapter_editor",
            supported_stage_types={
                ProductionStageType.CHAPTER_EDITING.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.EDITORIAL_DECISION.value,
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

        create_editorial = getattr(
            self.llm_service,
            "create_editorial_decision",
            None,
        )

        if create_editorial is None:
            raise NotImplementedError(
                "create_editorial_decision은 아직 "
                "ChapterGenerationService에 연결되지 "
                "않았습니다. 사용자 명령 기반 편집은 "
                "EditorStage.edit_chapter를 사용하세요."
            )

        payload = await create_editorial(
            draft=parse_artifact_content(draft_artifact),
            review=parse_artifact_content(review_artifact),
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_review"] = review_artifact.artifact_id

        return AgentResult.success(
            summary="편집 지시서를 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .EDITORIAL_DECISION
                        .value
                    ),
                    name=f"{payload['title']} 편집 지시서",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
        )


def _resolve_current_draft(
    context: Any,
) -> Any:
    for key in (
        "edited_draft",
        "revised_draft",
        "chapter_draft",
        "draft",
    ):
        value = _get_context_value(
            context,
            key,
            None,
        )

        if value is not None:
            return value

    artifacts = _get_context_value(
        context,
        "artifacts",
        {},
    )

    if not isinstance(artifacts, dict):
        return None

    for key in (
        "editor",
        "edited_draft",
        "reviser",
        "revised_draft",
        "chapter_draft",
        "writer",
        "draft",
    ):
        value = artifacts.get(key)

        if value is not None:
            return value

    return None


def _resolve_optional_artifact(
    context: Any,
    *,
    direct_keys: tuple[str, ...],
    artifact_keys: tuple[str, ...],
) -> Any:
    for key in direct_keys:
        value = _get_context_value(
            context,
            key,
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
        for key in artifact_keys:
            value = artifacts.get(key)

            if value is not None:
                return value

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
    previous_draft: dict[str, Any],
    edited_draft: dict[str, Any],
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
                {},
            ),
        }

    edit_history = result.get(
        "edit_history",
        [],
    )

    if not isinstance(edit_history, list):
        edit_history = []

    edit_history = list(edit_history)

    edit_history.append(
        {
            "before": previous_draft,
            "after": edited_draft,
            "mode": edited_draft.get(
                "metadata",
                {},
            ).get("edit_mode"),
            "scope": edited_draft.get(
                "metadata",
                {},
            ).get("edit_scope"),
            "revision": edited_draft.get(
                "metadata",
                {},
            ).get("revision"),
        }
    )

    result["edit_history"] = edit_history
    result["edited_draft"] = edited_draft

    # 최신 챕터 정본 교체
    result["chapter_draft"] = edited_draft
    result["draft"] = edited_draft

    artifacts = result.get("artifacts")

    if not isinstance(artifacts, dict):
        artifacts = {}

    artifacts = dict(artifacts)
    artifacts["editor"] = edited_draft
    artifacts["edited_draft"] = edited_draft
    artifacts["chapter_draft"] = edited_draft

    result["artifacts"] = artifacts
    result["current_artifact"] = edited_draft
    result["last_stage"] = "editor"

    return result
