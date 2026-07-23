from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReviserPromptBundle:
    """
    Reviser에게 전달할 System/User Prompt 묶음.
    """

    system_prompt: str
    user_prompt: str


def build_chapter_reviser_prompts(
    *,
    book_config: dict[str, Any],
    chapter_plan: dict[str, Any],
    research_artifact: dict[str, Any],
    chapter_draft: dict[str, Any],
    review_artifact: dict[str, Any],
    previous_chapters: list[dict[str, Any]] | None = None,
) -> ReviserPromptBundle:
    """
    Reviewer의 수정 지침을 반영해 챕터 전체 Markdown을
    다시 작성하기 위한 Prompt를 생성한다.

    출력 형식은 JSON이 아니라 순수 Markdown이다.
    """

    system_prompt = """
당신은 전문 출판 제작팀의 Reviser입니다.

당신의 역할은 Writer가 작성한 챕터 초안을 Reviewer의 검토 결과에
따라 수정하여 완성도 높은 챕터 Markdown을 만드는 것입니다.

반드시 다음 원칙을 지키십시오.

1. Chapter Plan의 목표와 필수 섹션을 유지합니다.
2. Research Artifact에서 확인된 사실과 근거만 사용합니다.
3. Review Artifact의 revision_instructions를 빠짐없이 반영합니다.
4. Reviewer가 unsupported 또는 not_verifiable로 판정한 주장은
   삭제하거나 근거 수준에 맞게 완화합니다.
5. 기존 초안의 장점은 유지합니다.
6. Reviewer가 지적하지 않은 부분도 문맥상 명백한 오류가 있으면
   함께 바로잡을 수 있습니다.
7. 챕터 전체를 완성된 Markdown으로 출력합니다.
8. 부분 수정문이나 변경사항 목록만 출력하지 않습니다.
9. JSON을 출력하지 않습니다.
10. Markdown 코드 블록으로 전체 결과를 감싸지 않습니다.
11. 출력은 반드시 하나의 H1 제목으로 시작합니다.
12. 원본의 chapter_id, metadata 같은 관리 정보를 출력하지 않습니다.
13. 출처 ID를 본문에 임의로 삽입하지 않습니다.
14. 제공되지 않은 사실, 수치, API 기능을 새로 만들어내지 않습니다.
15. Reviewer의 지시가 Research Artifact와 충돌하면
    Research Artifact의 근거 범위를 우선합니다.

출력 예시:

# 챕터 제목

## 첫 번째 섹션

수정된 본문...

## 두 번째 섹션

수정된 본문...
""".strip()

    user_payload = {
        "task": (
            "아래 초안을 Review Artifact의 지침에 따라 수정하고, "
            "완성된 챕터 전체를 Markdown으로 출력하세요."
        ),
        "book_config": _normalize_book_config(
            book_config
        ),
        "chapter_plan": _normalize_chapter_plan(
            chapter_plan
        ),
        "research_artifact": (
            _normalize_research_artifact(
                research_artifact
            )
        ),
        "chapter_draft": _normalize_chapter_draft(
            chapter_draft
        ),
        "review_artifact": (
            _normalize_review_artifact(
                review_artifact
            )
        ),
        "previous_chapters": (
            _normalize_previous_chapters(
                previous_chapters or []
            )
        ),
        "revision_requirements": {
            "return_complete_chapter": True,
            "output_format": "markdown",
            "preserve_supported_content": True,
            "apply_all_revision_instructions": True,
            "remove_unsupported_claims": True,
            "follow_required_sections": True,
            "do_not_return_json": True,
            "do_not_explain_changes": True,
        },
    }

    return ReviserPromptBundle(
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            user_payload,
            ensure_ascii=False,
            indent=2,
        ),
    )


def _normalize_book_config(
    book_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": book_config.get("title", ""),
        "description": book_config.get(
            "description",
            "",
        ),
        "target_reader": book_config.get(
            "target_reader",
            "",
        ),
        "book_style": book_config.get(
            "book_style",
            "",
        ),
        "goal": book_config.get("goal", ""),
        "language": book_config.get(
            "language",
            "ko",
        ),
        "book_type": book_config.get(
            "book_type",
            "",
        ),
        "writing_guidelines": book_config.get(
            "writing_guidelines",
            [],
        ),
    }


def _normalize_chapter_plan(
    chapter_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chapter_id": _get_chapter_id(
            chapter_plan
        ),
        "title": chapter_plan.get("title", ""),
        "description": chapter_plan.get(
            "description",
            "",
        ),
        "goal": chapter_plan.get("goal", ""),
        "key_points": chapter_plan.get(
            "key_points",
            [],
        ),
        "required_sections": chapter_plan.get(
            "required_sections",
            [],
        ),
        "source_ids": chapter_plan.get(
            "source_ids",
            [],
        ),
        "target_length": chapter_plan.get(
            "target_length",
            chapter_plan.get(
                "target_chars",
                0,
            ),
        ),
    }


def _normalize_research_artifact(
    research_artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": research_artifact.get(
            "artifact_type",
            "",
        ),
        "chapter_id": research_artifact.get(
            "chapter_id",
            "",
        ),
        "research_summary": research_artifact.get(
            "research_summary",
            "",
        ),
        "findings": research_artifact.get(
            "findings",
            [],
        ),
        "evidence": research_artifact.get(
            "evidence",
            [],
        ),
        "writing_guidance": research_artifact.get(
            "writing_guidance",
            [],
        ),
        "required_sections": research_artifact.get(
            "required_sections",
            [],
        ),
        "gaps": research_artifact.get(
            "gaps",
            [],
        ),
        "source_ids": research_artifact.get(
            "source_ids",
            [],
        ),
    }


def _normalize_chapter_draft(
    chapter_draft: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": chapter_draft.get(
            "artifact_type",
            "",
        ),
        "chapter_id": chapter_draft.get(
            "chapter_id",
            "",
        ),
        "title": chapter_draft.get(
            "title",
            "",
        ),
        "summary": chapter_draft.get(
            "summary",
            "",
        ),
        "markdown": chapter_draft.get(
            "markdown",
            "",
        ),
        "key_points": chapter_draft.get(
            "key_points",
            [],
        ),
        "source_ids": chapter_draft.get(
            "source_ids",
            [],
        ),
    }


def _normalize_review_artifact(
    review_artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": review_artifact.get(
            "artifact_type",
            "",
        ),
        "chapter_id": review_artifact.get(
            "chapter_id",
            "",
        ),
        "overall_score": review_artifact.get(
            "overall_score",
            0,
        ),
        "verdict": review_artifact.get(
            "verdict",
            "",
        ),
        "review_summary": review_artifact.get(
            "review_summary",
            "",
        ),
        "strengths": review_artifact.get(
            "strengths",
            [],
        ),
        "issues": review_artifact.get(
            "issues",
            [],
        ),
        "revision_instructions": review_artifact.get(
            "revision_instructions",
            [],
        ),
        "fact_check_items": review_artifact.get(
            "fact_check_items",
            [],
        ),
        "missing_sections": review_artifact.get(
            "missing_sections",
            [],
        ),
        "source_ids": review_artifact.get(
            "source_ids",
            [],
        ),
    }


def _normalize_previous_chapters(
    previous_chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for chapter in previous_chapters:
        if not isinstance(chapter, dict):
            continue

        normalized.append(
            {
                "chapter_id": _get_chapter_id(
                    chapter
                ),
                "title": chapter.get(
                    "title",
                    "",
                ),
                "summary": chapter.get(
                    "summary",
                    "",
                ),
                "key_points": chapter.get(
                    "key_points",
                    [],
                ),
            }
        )

    return normalized


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
