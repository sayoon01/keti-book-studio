from __future__ import annotations

from typing import Any

from backend.generation.handlers.structured_json_handler import (
    StructuredJsonHandler,
    metadata_to_dict,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_reviewer import (
    build_chapter_reviewer_prompts,
)
from backend.generation.validators import (
    validate_review_artifact,
)
from backend.infrastructure.llm import OllamaClient


class ReviewerHandler:
    """
    일반 Reviewer 역할 전용 Handler.

    기술 리뷰가 필요한지 판단하는 책임은
    ChapterGenerationService 또는 이후 Review Orchestrator가 담당한다.
    """

    def __init__(
        self,
        *,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        self._generator = StructuredJsonHandler(
            role=GenerationRole.REVIEWER,
            client=client,
            model_router=model_router,
            max_attempts=max_attempts,
        )

    async def run(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        research_artifact: dict[str, Any],
        chapter_draft: dict[str, Any],
        previous_chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _validate_input_artifacts(
            research_artifact=research_artifact,
            chapter_draft=chapter_draft,
        )

        prompts = build_chapter_reviewer_prompts(
            book_config=book_config,
            chapter_plan=chapter_plan,
            research_artifact=research_artifact,
            chapter_draft=chapter_draft,
            previous_chapters=previous_chapters,
        )

        chapter_id = _get_chapter_id(
            chapter_plan,
            chapter_draft,
        )

        chapter_title = str(
            chapter_draft.get("title")
            or chapter_plan.get("title")
            or ""
        ).strip()

        def enrich_payload(
            payload: dict[str, Any],
            metadata: Any,
            attempt: int,
        ) -> dict[str, Any]:
            result = dict(payload)

            result["chapter_id"] = chapter_id

            if not str(
                result.get("title", "")
            ).strip():
                result["title"] = chapter_title

            result["metadata"] = {
                **metadata_to_dict(metadata),
                "role": GenerationRole.REVIEWER.value,
                "response_format": "json",
                "attempt": attempt,
            }

            return result

        return await self._generator.generate(
            system_prompt=prompts.system_prompt,
            user_prompt=prompts.user_prompt,
            validator=validate_review_artifact,
            enrich_payload=enrich_payload,
            operation_name="Chapter Reviewer",
        )


def _validate_input_artifacts(
    *,
    research_artifact: dict[str, Any],
    chapter_draft: dict[str, Any],
) -> None:
    research_type = str(
        research_artifact.get(
            "artifact_type",
            "",
        )
    ).strip()

    if research_type != "RESEARCH_ARTIFACT":
        raise ValueError(
            "Reviewer에는 정본 RESEARCH_ARTIFACT가 필요합니다. "
            f"actual={research_type!r}"
        )

    draft_type = str(
        chapter_draft.get(
            "artifact_type",
            "",
        )
    ).strip()

    if draft_type != "CHAPTER_DRAFT":
        raise ValueError(
            "Reviewer에는 CHAPTER_DRAFT가 필요합니다. "
            f"actual={draft_type!r}"
        )


def _get_chapter_id(
    chapter_plan: dict[str, Any],
    chapter_draft: dict[str, Any],
) -> str:
    value = (
        chapter_draft.get("chapter_id")
        or chapter_plan.get("chapter_id")
        or chapter_plan.get("unit_id")
        or chapter_plan.get("id")
        or ""
    )

    normalized = str(value).strip()

    if not normalized:
        raise ValueError(
            "Reviewer 입력에 chapter_id가 필요합니다."
        )

    return normalized
