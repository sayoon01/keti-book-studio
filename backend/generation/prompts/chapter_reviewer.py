from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReviewerPromptBundle:
    system_prompt: str
    user_prompt: str


def build_chapter_reviewer_prompts(
    *,
    book_config: dict[str, Any],
    chapter_plan: dict[str, Any],
    research_artifact: dict[str, Any],
    chapter_draft: dict[str, Any],
    previous_chapters: list[dict[str, Any]] | None = None,
) -> ReviewerPromptBundle:
    """
    Chapter Draft를 검토하기 위한 Reviewer Prompt를 생성한다.

    Reviewer는 본문을 직접 수정하지 않는다.
    문제 진단과 수정 지침만 JSON으로 반환한다.
    """

    system_prompt = """
당신은 전문 출판 제작팀의 Reviewer입니다.

당신의 역할은 Writer가 작성한 챕터 초안을 검토하여
문제점, 강점, 사실 검증 결과와 구체적인 수정 지침을
구조화된 JSON으로 제공하는 것입니다.

반드시 다음 원칙을 지키십시오.

1. 본문을 직접 다시 작성하지 않습니다.
2. 제공된 Research Artifact와 Chapter Plan을 기준으로 검토합니다.
3. 제공된 근거에서 확인할 수 없는 주장은 unsupported 또는
   not_verifiable로 표시합니다.
4. 단순한 취향이 아니라 독자, 책 목적, 챕터 목표를 기준으로 평가합니다.
5. 문제 위치를 확인할 수 있으면 location에 제목이나 문장을 기록합니다.
6. revision_instructions는 Reviser가 바로 수행할 수 있게 작성합니다.
7. 코드가 있는 경우 문법, 일관성, 설명과 코드의 대응 여부를 검토합니다.
8. JSON 객체 하나만 출력합니다.
9. JSON 앞뒤에 Markdown 코드 블록이나 설명을 붙이지 않습니다.
10. overall_score는 0부터 100 사이의 정수입니다.

판정 기준:

- approved:
  치명적·중대한 문제가 없고 바로 출판 가능한 상태

- minor_revision:
  전체 구조는 적절하지만 표현, 예시, 일부 설명 보완이 필요함

- major_revision:
  핵심 설명 누락, 구조 문제, 근거 부족 또는 중요한 오류가 있음

- rejected:
  챕터 목표를 충족하지 못하거나 전체 재작성이 필요함

반드시 다음 JSON 구조를 사용하십시오.

{
  "chapter_id": "챕터 식별자",
  "title": "검토 대상 챕터 제목",
  "overall_score": 0,
  "verdict": "approved | minor_revision | major_revision | rejected",
  "review_summary": "전체 검토 요약",
  "strengths": [
    "잘 작성된 점"
  ],
  "issues": [
    {
      "category": "accuracy | completeness | structure | clarity | style | evidence | consistency | code | other",
      "severity": "critical | major | minor | suggestion",
      "location": "문제가 있는 섹션 또는 문장",
      "description": "문제 설명",
      "recommendation": "구체적인 수정 방법",
      "source_ids": ["source-001"]
    }
  ],
  "revision_instructions": [
    "Reviser가 수행할 구체적인 수정 지침"
  ],
  "fact_check_items": [
    {
      "claim": "본문에 포함된 주장",
      "status": "supported | partially_supported | unsupported | not_verifiable",
      "explanation": "판정 이유",
      "source_ids": ["source-001"]
    }
  ],
  "missing_sections": [
    "챕터 계획에는 있지만 초안에서 부족하거나 빠진 섹션"
  ],
  "source_ids": [
    "검토에 사용한 source_id"
  ]
}
""".strip()

    user_payload = {
        "task": (
            "아래 Chapter Draft를 Chapter Plan과 "
            "Research Artifact에 근거하여 검토하세요."
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
        "previous_chapters": (
            _normalize_previous_chapters(
                previous_chapters or []
            )
        ),
        "review_requirements": {
            "evaluate_goal_alignment": True,
            "evaluate_required_sections": True,
            "evaluate_accuracy": True,
            "evaluate_clarity": True,
            "evaluate_structure": True,
            "evaluate_source_support": True,
            "do_not_rewrite_chapter": True,
            "output_format": "json",
        },
    }

    return ReviewerPromptBundle(
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
    research: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chapter_id": research.get(
            "chapter_id",
            "",
        ),
        "research_summary": research.get(
            "research_summary",
            "",
        ),
        "findings": research.get(
            "findings",
            [],
        ),
        "evidence": research.get(
            "evidence",
            [],
        ),
        "writing_guidance": research.get(
            "writing_guidance",
            [],
        ),
        "required_sections": research.get(
            "required_sections",
            [],
        ),
        "gaps": research.get("gaps", []),
        "source_ids": research.get(
            "source_ids",
            [],
        ),
    }


def _normalize_chapter_draft(
    chapter_draft: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chapter_id": chapter_draft.get(
            "chapter_id",
            "",
        ),
        "title": chapter_draft.get("title", ""),
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
