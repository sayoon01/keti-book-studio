from __future__ import annotations

import logging
from typing import Any

from backend.generation.handlers.base_structured_handler import (
    BaseStructuredHandler,
    PromptBundleProtocol,
    StructuredExecutionContext,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_researcher import (
    build_chapter_researcher_prompts,
)
from backend.generation.validators import (
    validate_research_artifact,
)
from backend.infrastructure.llm import OllamaClient


logger = logging.getLogger(__name__)


class ResearchHandler(
    BaseStructuredHandler[dict[str, Any]]
):
    """
    Researcher 역할 전용 Handler.

    공통 JSON 생성 과정은 BaseStructuredHandler가 담당한다.
    """

    role = GenerationRole.RESEARCHER
    operation_name = "Chapter Researcher"
    validator = staticmethod(
        validate_research_artifact
    )

    def __init__(
        self,
        *,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        super().__init__(
            client=client,
            model_router=model_router,
            max_attempts=max_attempts,
        )

    async def run(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        sources: list[dict[str, Any]],
        previous_chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Writer가 사용할 RESEARCH_ARTIFACT를 생성한다.
        """

        return await self._execute(
            book_config=book_config,
            chapter_plan=chapter_plan,
            sources=sources,
            previous_chapters=previous_chapters,
        )

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        book_config = inputs.get("book_config")
        chapter_plan = inputs.get("chapter_plan")
        sources = inputs.get("sources")
        previous_chapters = inputs.get(
            "previous_chapters"
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "book_config는 dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "chapter_plan은 dictionary여야 합니다."
            )

        if not _get_chapter_id(chapter_plan):
            raise ValueError(
                "chapter_plan에 chapter_id가 필요합니다."
            )

        if not isinstance(sources, list):
            raise TypeError(
                "sources는 list여야 합니다."
            )

        if not isinstance(
            previous_chapters,
            list,
        ):
            raise TypeError(
                "previous_chapters는 list여야 합니다."
            )

    def _build_prompts(
        self,
        **inputs: Any,
    ) -> PromptBundleProtocol:
        return build_chapter_researcher_prompts(
            book_config=inputs["book_config"],
            chapter_plan=inputs["chapter_plan"],
            sources=inputs["sources"],
            previous_chapters=(
                inputs["previous_chapters"]
            ),
        )

    def _enrich_payload(
        self,
        *,
        payload: dict[str, Any],
        execution_context: StructuredExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        chapter_plan = inputs["chapter_plan"]

        chapter_id = _get_chapter_id(
            chapter_plan
        )

        chapter_title = str(
            chapter_plan.get("title", "")
        ).strip()

        result = dict(payload)

        # LLM이 다른 ID를 생성해도 입력 Plan의 ID를 정본으로 사용한다.
        result["chapter_id"] = chapter_id

        if not str(
            result.get("title", "")
        ).strip():
            result["title"] = chapter_title

        result["metadata"] = self._build_metadata(
            execution_context
        )

        return result

    def _log_completion(
        self,
        *,
        artifact: dict[str, Any],
        execution_context: StructuredExecutionContext,
    ) -> None:
        logger.info(
            "%s completed: chapter_id=%s model=%s "
            "attempt=%s findings=%s evidence=%s",
            self.operation_name,
            artifact.get("chapter_id"),
            execution_context.model,
            execution_context.attempt,
            len(artifact.get("findings", [])),
            len(artifact.get("evidence", [])),
        )


def _get_chapter_id(
    chapter_plan: dict[str, Any],
) -> str:
    value = (
        chapter_plan.get("chapter_id")
        or chapter_plan.get("unit_id")
        or chapter_plan.get("id")
        or ""
    )

    return str(value).strip()
