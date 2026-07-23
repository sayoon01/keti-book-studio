from __future__ import annotations

import logging
import re
from typing import Any

from backend.generation.handlers.base_text_handler import (
    BaseTextHandler,
    TextExecutionContext,
    TextPromptBundleProtocol,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_reviser import (
    build_chapter_reviser_prompts,
)
from backend.generation.validators import (
    validate_chapter_draft,
)
from backend.infrastructure.llm import OllamaClient


logger = logging.getLogger(__name__)


class ReviserHandler(
    BaseTextHandler[dict[str, Any]]
):
    """
    Reviewer의 검토 결과를 반영하여
    새로운 CHAPTER_DRAFT를 생성한다.
    """

    role = GenerationRole.REVISER
    operation_name = "Chapter Reviser"

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
        review_artifact: dict[str, Any],
        previous_chapters: list[dict[str, Any]],
        revision_number: int = 1,
    ) -> dict[str, Any]:
        """
        리뷰 지침을 반영한 CHAPTER_DRAFT 새 버전을 생성한다.
        """

        return await self._execute(
            book_config=book_config,
            chapter_plan=chapter_plan,
            research_artifact=research_artifact,
            chapter_draft=chapter_draft,
            review_artifact=review_artifact,
            previous_chapters=previous_chapters,
            revision_number=revision_number,
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
        review_artifact = inputs.get(
            "review_artifact"
        )
        previous_chapters = inputs.get(
            "previous_chapters"
        )
        revision_number = inputs.get(
            "revision_number"
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
            review_artifact,
            dict,
        ):
            raise TypeError(
                "review_artifact는 "
                "dictionary여야 합니다."
            )

        if not isinstance(
            previous_chapters,
            list,
        ):
            raise TypeError(
                "previous_chapters는 list여야 합니다."
            )

        if (
            not isinstance(revision_number, int)
            or isinstance(revision_number, bool)
            or revision_number <= 0
        ):
            raise ValueError(
                "revision_number는 1 이상의 정수여야 합니다."
            )

        research_type = str(
            research_artifact.get(
                "artifact_type",
                "",
            )
        ).strip()

        if research_type != "RESEARCH_ARTIFACT":
            raise ValueError(
                "Reviser에는 RESEARCH_ARTIFACT가 필요합니다. "
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
                "Reviser에는 CHAPTER_DRAFT가 필요합니다. "
                f"actual={draft_type!r}"
            )

        review_type = str(
            review_artifact.get(
                "artifact_type",
                "",
            )
        ).strip()

        if review_type != "REVIEW_ARTIFACT":
            raise ValueError(
                "Reviser에는 REVIEW_ARTIFACT가 필요합니다. "
                f"actual={review_type!r}"
            )

        plan_chapter_id = _get_chapter_id(
            chapter_plan
        )

        research_chapter_id = _get_chapter_id(
            research_artifact
        )

        draft_chapter_id = _get_chapter_id(
            chapter_draft
        )

        review_chapter_id = _get_chapter_id(
            review_artifact
        )

        if not draft_chapter_id:
            raise ValueError(
                "chapter_draft에 chapter_id가 필요합니다."
            )

        chapter_ids = {
            chapter_id
            for chapter_id in (
                plan_chapter_id,
                research_chapter_id,
                draft_chapter_id,
                review_chapter_id,
            )
            if chapter_id
        }

        if len(chapter_ids) > 1:
            raise ValueError(
                "Reviser 입력 Artifact의 chapter_id가 "
                "일치하지 않습니다. "
                f"plan={plan_chapter_id!r}, "
                f"research={research_chapter_id!r}, "
                f"draft={draft_chapter_id!r}, "
                f"review={review_chapter_id!r}"
            )

        verdict = str(
            review_artifact.get(
                "verdict",
                "",
            )
        ).strip()

        if verdict not in {
            "approved",
            "minor_revision",
            "major_revision",
            "rejected",
        }:
            raise ValueError(
                "review_artifact.verdict가 "
                "올바르지 않습니다. "
                f"actual={verdict!r}"
            )

    def _build_prompts(
        self,
        **inputs: Any,
    ) -> TextPromptBundleProtocol:
        return build_chapter_reviser_prompts(
            book_config=inputs["book_config"],
            chapter_plan=inputs["chapter_plan"],
            research_artifact=(
                inputs["research_artifact"]
            ),
            chapter_draft=(
                inputs["chapter_draft"]
            ),
            review_artifact=(
                inputs["review_artifact"]
            ),
            previous_chapters=(
                inputs["previous_chapters"]
            ),
        )

    def _clean_generated_text(
        self,
        text: str,
    ) -> str:
        cleaned = super()._clean_generated_text(
            text
        )

        # 일부 모델이 출력 앞에 설명을 붙이는 경우
        # 최초 H1부터 본문으로 사용한다.
        first_h1_match = re.search(
            r"(?m)^#\s+.+$",
            cleaned,
        )

        if first_h1_match is not None:
            cleaned = cleaned[
                first_h1_match.start():
            ]

        return cleaned.strip()

    def _build_artifact(
        self,
        *,
        generated_text: str,
        execution_context: TextExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        chapter_plan = inputs["chapter_plan"]
        chapter_draft = inputs["chapter_draft"]
        review_artifact = inputs["review_artifact"]
        research_artifact = inputs[
            "research_artifact"
        ]
        revision_number = inputs[
            "revision_number"
        ]

        chapter_id = (
            _get_chapter_id(chapter_draft)
            or _get_chapter_id(chapter_plan)
        )

        title = (
            _extract_markdown_title(
                generated_text
            )
            or str(
                chapter_draft.get("title")
                or chapter_plan.get("title")
                or ""
            ).strip()
        )

        summary = _build_revised_summary(
            chapter_draft=chapter_draft,
            review_artifact=review_artifact,
        )

        key_points = _resolve_key_points(
            chapter_plan=chapter_plan,
            chapter_draft=chapter_draft,
            research_artifact=research_artifact,
        )

        source_ids = _merge_string_lists(
            chapter_draft.get(
                "source_ids",
                [],
            ),
            research_artifact.get(
                "source_ids",
                [],
            ),
            review_artifact.get(
                "source_ids",
                [],
            ),
        )

        metadata = {
            **self._build_metadata(
                execution_context
            ),
            "stage": "reviser",
            "revision": revision_number,
            "based_on_review": True,
            "review_score": review_artifact.get(
                "overall_score"
            ),
            "review_verdict": review_artifact.get(
                "verdict"
            ),
            "previous_artifact_type": (
                chapter_draft.get(
                    "artifact_type"
                )
            ),
        }

        payload = {
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": chapter_id,
            "title": title,
            "summary": summary,
            "markdown": generated_text,
            "key_points": key_points,
            "source_ids": source_ids,
            "metadata": metadata,
        }

        return validate_chapter_draft(
            payload,
            minimum_markdown_length=300,
        )

    def _log_completion(
        self,
        *,
        artifact: dict[str, Any],
        execution_context: TextExecutionContext,
    ) -> None:
        logger.info(
            "%s completed: chapter_id=%s model=%s "
            "attempt=%s revision=%s markdown_length=%s",
            self.operation_name,
            artifact.get("chapter_id"),
            execution_context.model,
            execution_context.attempt,
            artifact.get(
                "metadata",
                {},
            ).get("revision"),
            len(
                str(
                    artifact.get(
                        "markdown",
                        "",
                    )
                )
            ),
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


def _extract_markdown_title(
    markdown: str,
) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            return stripped[2:].strip()

    return ""


def _build_revised_summary(
    *,
    chapter_draft: dict[str, Any],
    review_artifact: dict[str, Any],
) -> str:
    """
    Reviser 모델은 순수 Markdown만 반환하므로 summary는
    기존 Draft와 Review Summary를 이용해 Python에서 조립한다.
    """

    original_summary = str(
        chapter_draft.get(
            "summary",
            "",
        )
    ).strip()

    verdict = str(
        review_artifact.get(
            "verdict",
            "",
        )
    ).strip()

    if original_summary:
        return (
            f"{original_summary} "
            f"Reviewer의 {verdict} 검토 결과를 반영하여 "
            "내용과 구조를 보완한 개정본입니다."
        )

    return (
        f"Reviewer의 {verdict} 검토 결과와 수정 지침을 "
        "반영한 챕터 개정본입니다."
    )


def _resolve_key_points(
    *,
    chapter_plan: dict[str, Any],
    chapter_draft: dict[str, Any],
    research_artifact: dict[str, Any],
) -> list[str]:
    plan_key_points = chapter_plan.get(
        "key_points",
        [],
    )

    if isinstance(plan_key_points, list):
        normalized = _normalize_string_list(
            plan_key_points
        )

        if normalized:
            return normalized

    draft_key_points = chapter_draft.get(
        "key_points",
        [],
    )

    if isinstance(draft_key_points, list):
        normalized = _normalize_string_list(
            draft_key_points
        )

        if normalized:
            return normalized

    findings = research_artifact.get(
        "findings",
        [],
    )

    result: list[str] = []

    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue

            topic = str(
                finding.get("topic", "")
            ).strip()

            if topic and topic not in result:
                result.append(topic)

    return result


def _merge_string_lists(
    *values: Any,
) -> list[str]:
    result: list[str] = []

    for value in values:
        if not isinstance(value, list):
            continue

        for item in value:
            text = str(item).strip()

            if text and text not in result:
                result.append(text)

    return result


def _normalize_string_list(
    value: list[Any],
) -> list[str]:
    result: list[str] = []

    for item in value:
        text = str(item).strip()

        if text and text not in result:
            result.append(text)

    return result
