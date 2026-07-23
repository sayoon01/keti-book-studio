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


class ResearcherStage:
    """
    챕터 집필 전 조사 단계를 실행한다.

    이 Stage는 직접 LLM을 호출하지 않는다.

    호출 흐름:
        ResearcherStage
        → ChapterGenerationService.research_chapter()
        → ModelRouter
        → OllamaClient
    """

    name = "researcher"
    stage_name = "researcher"
    artifact_type = "RESEARCH_ARTIFACT"

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
        """
        StageRunner에서 사용할 기본 실행 메서드.
        """

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

        sources = _get_context_value(
            context,
            "sources",
            [],
        )

        previous_chapters = _get_context_value(
            context,
            "previous_chapters",
            [],
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "ResearcherStage book_config는 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "ResearcherStage chapter_plan은 "
                "dictionary여야 합니다."
            )

        if not isinstance(sources, list):
            sources = []

        if not isinstance(previous_chapters, list):
            previous_chapters = []

        logger.info(
            "ResearcherStage started: chapter_id=%s",
            chapter_plan.get("chapter_id")
            or chapter_plan.get("unit_id")
            or chapter_plan.get("id"),
        )

        research_artifact = (
            await self._generation_service.research_chapter(
                book_config=book_config,
                chapter_plan=chapter_plan,
                sources=sources,
                previous_chapters=previous_chapters,
            )
        )

        logger.info(
            "ResearcherStage completed: "
            "chapter_id=%s findings=%s",
            research_artifact.get("chapter_id"),
            len(
                research_artifact.get(
                    "findings",
                    [],
                )
            ),
        )

        return _merge_result_into_context(
            context=context,
            research_artifact=research_artifact,
        )

    async def run(
        self,
        context: Any,
    ) -> dict[str, Any]:
        """
        구 StageRunner가 run()을 호출하는 경우를 위한 호환 메서드.
        """

        return await self.execute(context)


class ResearchAgent(BasePublishingAgent):
    """
    ProductionEngine용 Researcher Stage Handler.

    ResearcherStage와 동일하게 ChapterGenerationService를 호출한다.
    """

    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.RESEARCHER.value,
            name="chapter_researcher",
            supported_stage_types={
                ProductionStageType.CHAPTER_RESEARCH.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_PLAN.value,
            },
            output_artifact_types={
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
        )
        self.llm_service = (
            llm_service or ChapterGenerationService()
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        plan_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        plan = parse_artifact_content(plan_artifact)

        sources = [
            {
                "source_id": getattr(
                    source,
                    "source_id",
                    getattr(source, "id", ""),
                ),
                "title": getattr(source, "title", ""),
                "type": getattr(
                    source,
                    "source_type",
                    getattr(source, "type", ""),
                ),
                "content": getattr(
                    source,
                    "content",
                    getattr(source, "text", ""),
                ),
            }
            for source in context.sources
        ]

        book_config = {
            "title": context.book.title,
            "description": context.book.description,
            "target_reader": context.book.target_reader,
            "goal": context.book.purpose,
            "language": context.book.language,
        }

        payload = await self.llm_service.research_chapter(
            book_config=book_config,
            chapter_plan=plan,
            sources=sources,
            previous_chapters=[],
        )

        payload["based_on_plan"] = plan_artifact.artifact_id

        unit_title = (
            context.unit.title
            if context.unit
            else payload.get("title", "Untitled")
        )

        return AgentResult.success(
            summary="챕터 조사 보고서를 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType.RESEARCH_REPORT.value
                    ),
                    name=f"{unit_title} 조사 보고서",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "source_count": len(sources),
                "findings": len(
                    payload.get("findings", [])
                ),
            },
        )


def _get_context_value(
    context: Any,
    key: str,
    fallback: Any,
) -> Any:
    """
    context가 dictionary 또는 객체인 경우를 모두 지원한다.
    """

    if isinstance(context, dict):
        return context.get(key, fallback)

    return getattr(context, key, fallback)


def _merge_result_into_context(
    *,
    context: Any,
    research_artifact: dict[str, Any],
) -> dict[str, Any]:
    """
    Stage 실행 결과를 다음 Stage가 사용할 수 있게 반환한다.

    기존 context가 dictionary인 경우 원본을 복사해서
    research 및 artifacts를 추가한다.
    """

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
            "sources": _get_context_value(
                context,
                "sources",
                [],
            ),
            "previous_chapters": _get_context_value(
                context,
                "previous_chapters",
                [],
            ),
        }

    result["research"] = research_artifact
    result["research_artifact"] = research_artifact

    artifacts = result.get("artifacts")

    if not isinstance(artifacts, dict):
        artifacts = {}

    artifacts = dict(artifacts)
    artifacts["research"] = research_artifact

    result["artifacts"] = artifacts
    result["current_artifact"] = research_artifact
    result["last_stage"] = "researcher"

    return result
