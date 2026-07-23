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
from backend.generation.prompts.chapter_reviewer import (
    build_chapter_reviewer_prompts,
)
from backend.generation.validators import (
    validate_review_artifact,
)
from backend.infrastructure.llm import OllamaClient


logger = logging.getLogger(__name__)


class ReviewerHandler(
    BaseStructuredHandler[dict[str, Any]]
):
    """
    Reviewer 역할 전용 Handler.

    본문을 직접 수정하지 않고
    REVIEW_ARTIFACT를 생성한다.
    """

    role = GenerationRole.REVIEWER
    operation_name = "Chapter Reviewer"
    validator = staticmethod(
        validate_review_artifact
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
        research_artifact: dict[str, Any],
        chapter_draft: dict[str, Any],
        previous_chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        CHAPTER_DRAFT를 검토하여 REVIEW_ARTIFACT를 생성한다.
        """

        return await self._execute(
            book_config=book_config,
            chapter_plan=chapter_plan,
            research_artifact=research_artifact,
            chapter_draft=chapter_draft,
            previous_chapters=previous_chapters,
        )

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        book_config = inputs.get("book_config")
        chapter_plan = inputs.get("chapter_plan")
        research_artifact = inputs.get(
            "research_artifact"
        )
        chapter_draft = inputs.get(
            "chapter_draft"
        )
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

        if not isinstance(
            research_artifact,
            dict,
        ):
            raise TypeError(
                "research_artifact는 "
                "dictionary여야 합니다."
            )

        if not isinstance(chapter_draft, dict):
            raise TypeError(
                "chapter_draft는 dictionary여야 합니다."
            )

        if not isinstance(
            previous_chapters,
            list,
        ):
            raise TypeError(
                "previous_chapters는 list여야 합니다."
            )

        research_type = str(
            research_artifact.get(
                "artifact_type",
                "",
            )
        ).strip()

        if research_type != "RESEARCH_ARTIFACT":
            raise ValueError(
                "Reviewer에는 정본 RESEARCH_ARTIFACT가 "
                "필요합니다. "
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

        research_chapter_id = _get_chapter_id(
            research_artifact
        )

        draft_chapter_id = _get_chapter_id(
            chapter_draft
        )

        plan_chapter_id = _get_chapter_id(
            chapter_plan
        )

        if not draft_chapter_id:
            raise ValueError(
                "chapter_draft에 chapter_id가 필요합니다."
            )

        if (
            research_chapter_id
            and research_chapter_id
            != draft_chapter_id
        ):
            raise ValueError(
                "Research Artifact와 Chapter Draft의 "
                "chapter_id가 일치하지 않습니다. "
                f"research={research_chapter_id!r}, "
                f"draft={draft_chapter_id!r}"
            )

        if (
            plan_chapter_id
            and plan_chapter_id
            != draft_chapter_id
        ):
            raise ValueError(
                "Chapter Plan과 Chapter Draft의 "
                "chapter_id가 일치하지 않습니다. "
                f"plan={plan_chapter_id!r}, "
                f"draft={draft_chapter_id!r}"
            )

    def _build_prompts(
        self,
        **inputs: Any,
    ) -> PromptBundleProtocol:
        return build_chapter_reviewer_prompts(
            book_config=inputs["book_config"],
            chapter_plan=inputs["chapter_plan"],
            research_artifact=(
                inputs["research_artifact"]
            ),
            chapter_draft=(
                inputs["chapter_draft"]
            ),
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
        chapter_draft = inputs["chapter_draft"]

        chapter_id = (
            _get_chapter_id(chapter_draft)
            or _get_chapter_id(chapter_plan)
        )

        chapter_title = str(
            chapter_draft.get("title")
            or chapter_plan.get("title")
            or ""
        ).strip()

        result = dict(payload)

        # LLM 출력보다 파이프라인 입력 Artifact의 ID가 우선이다.
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
            "attempt=%s score=%s verdict=%s issues=%s",
            self.operation_name,
            artifact.get("chapter_id"),
            execution_context.model,
            execution_context.attempt,
            artifact.get("overall_score"),
            artifact.get("verdict"),
            len(artifact.get("issues", [])),
        )


def _get_chapter_id(
    payload: dict[str, Any],
) -> str:
    value = (
        payload.get("chapter_id")
        or payload.get("unit_id")
        or payload.get("id")
        or ""
    )

    return str(value).strip()
