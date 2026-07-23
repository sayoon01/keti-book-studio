from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.generation.schemas import (
    EditorCommand,
    EditorScope,
    get_default_editor_instruction,
)


@dataclass(frozen=True, slots=True)
class EditorPromptBundle:
    """
    Editor 모델 호출에 사용하는 Prompt 묶음.
    """

    system_prompt: str
    user_prompt: str


def build_chapter_editor_prompts(
    *,
    book_config: dict[str, Any],
    chapter_plan: dict[str, Any],
    chapter_draft: dict[str, Any],
    editor_command: EditorCommand,
    research_artifact: dict[str, Any] | None = None,
    review_artifact: dict[str, Any] | None = None,
    previous_chapters: list[dict[str, Any]] | None = None,
) -> EditorPromptBundle:
    """
    사용자 명령에 따라 챕터 또는 선택 영역을 편집하기 위한
    Prompt를 생성한다.
    """

    if editor_command.scope == EditorScope.CHAPTER:
        system_prompt = _build_chapter_system_prompt()
        editable_text = str(
            chapter_draft.get("markdown", "")
        ).strip()
    else:
        system_prompt = _build_selection_system_prompt()

        if editor_command.selection is None:
            raise ValueError(
                "selection 편집에는 selection이 필요합니다."
            )

        editable_text = editor_command.selection.text

    default_instruction = (
        get_default_editor_instruction(
            editor_command.mode
        )
    )

    user_instruction = (
        editor_command.instruction.strip()
    )

    final_instruction = _merge_instructions(
        default_instruction=default_instruction,
        user_instruction=user_instruction,
    )

    user_payload = {
        "task": "사용자의 편집 명령을 수행하세요.",
        "edit_command": {
            "mode": editor_command.mode.value,
            "scope": editor_command.scope.value,
            "instruction": final_instruction,
            "preserve_markdown_structure": (
                editor_command.preserve_markdown_structure
            ),
        },
        "book_config": _normalize_book_config(
            book_config
        ),
        "chapter_plan": _normalize_chapter_plan(
            chapter_plan
        ),
        "chapter_context": {
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
            "key_points": chapter_draft.get(
                "key_points",
                [],
            ),
        },
        "editable_text": editable_text,
        "research_context": (
            _normalize_research_artifact(
                research_artifact
            )
            if isinstance(research_artifact, dict)
            else None
        ),
        "review_context": (
            _normalize_review_artifact(
                review_artifact
            )
            if isinstance(review_artifact, dict)
            else None
        ),
        "previous_chapters": (
            _normalize_previous_chapters(
                previous_chapters or []
            )
        ),
        "output_requirements": {
            "output_only_edited_markdown": True,
            "do_not_return_json": True,
            "do_not_explain_changes": True,
            "do_not_wrap_in_markdown_fence": True,
            "do_not_invent_facts": True,
            "preserve_original_language": True,
        },
    }

    return EditorPromptBundle(
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            user_payload,
            ensure_ascii=False,
            indent=2,
        ),
    )


def _build_chapter_system_prompt() -> str:
    return """
당신은 전문 출판 편집자입니다.

사용자의 편집 명령에 따라 제공된 챕터 전체를 수정하십시오.

반드시 다음 원칙을 따르십시오.

1. 출력은 수정된 챕터 전체 Markdown이어야 합니다.
2. 하나의 H1 제목으로 시작하십시오.
3. 수정 설명, 변경 내역, 사과문을 출력하지 마십시오.
4. JSON을 출력하지 마십시오.
5. 전체 결과를 Markdown 코드 블록으로 감싸지 마십시오.
6. 사용자 명령과 관계없는 사실은 임의로 추가하지 마십시오.
7. Research Context가 있다면 해당 근거 범위 안에서만 내용을 추가하십시오.
8. 기존 제목과 섹션 구조는 사용자의 명령과 충돌하지 않는 범위에서 유지하십시오.
9. 출처 ID나 내부 metadata를 본문에 출력하지 마십시오.
10. 사용자 명령이 내용 축소를 요구하면 핵심 정보는 유지하십시오.
11. 사용자 명령이 내용 확장을 요구하면 근거 없는 기능, 수치, 사례를 만들지 마십시오.
12. 기존 Markdown의 코드 블록, 표, 목록 구조를 가능한 한 보존하십시오.
""".strip()


def _build_selection_system_prompt() -> str:
    return """
당신은 전문 출판 편집자입니다.

사용자가 선택한 Markdown 영역만 편집하십시오.

반드시 다음 원칙을 따르십시오.

1. 출력은 선택 영역을 대체할 Markdown만 포함해야 합니다.
2. 챕터 전체를 출력하지 마십시오.
3. 수정 설명이나 변경 내역을 출력하지 마십시오.
4. JSON을 출력하지 마십시오.
5. 결과를 Markdown 코드 블록으로 감싸지 마십시오.
6. 선택 영역 밖의 내용을 임의로 작성하지 마십시오.
7. 선택 영역의 앞뒤 문맥과 자연스럽게 연결되도록 작성하십시오.
8. Research Context가 있다면 해당 근거 범위 안에서만 내용을 추가하십시오.
9. 출처 ID나 내부 metadata를 출력하지 마십시오.
10. 선택 영역이 제목이라면 같은 수준의 Markdown 제목 형식을 유지하십시오.
11. 선택 영역이 표나 목록이라면 기존 Markdown 형식을 가능한 한 유지하십시오.
""".strip()


def _merge_instructions(
    *,
    default_instruction: str,
    user_instruction: str,
) -> str:
    if default_instruction and user_instruction:
        return (
            f"{default_instruction}\n\n"
            f"추가 사용자 지침:\n{user_instruction}"
        )

    if user_instruction:
        return user_instruction

    return default_instruction


def _normalize_book_config(
    book_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": book_config.get("title", ""),
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
        "writing_guidelines": book_config.get(
            "writing_guidelines",
            [],
        ),
    }


def _normalize_chapter_plan(
    chapter_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chapter_id": (
            chapter_plan.get("chapter_id")
            or chapter_plan.get("unit_id")
            or chapter_plan.get("id")
            or ""
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
        "gaps": research_artifact.get(
            "gaps",
            [],
        ),
        "source_ids": research_artifact.get(
            "source_ids",
            [],
        ),
    }


def _normalize_review_artifact(
    review_artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
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
                "chapter_id": chapter.get(
                    "chapter_id",
                    "",
                ),
                "title": chapter.get(
                    "title",
                    "",
                ),
                "summary": chapter.get(
                    "summary",
                    "",
                ),
            }
        )

    return normalized


# ---------------------------------------------------------------------------
# Legacy editorial-decision prompts (EditorAgent 호환)
# ---------------------------------------------------------------------------

EDITOR_SYSTEM_PROMPT = """
당신은 전문 출판사의 책임 편집자입니다.

초안과 리뷰 보고서를 바탕으로 Reviser가 바로 실행할 수 있는
구체적인 편집 지시서를 작성하세요.

단순히 '더 명확하게 작성하세요'라고 하지 마세요.
어디를, 왜, 어떻게 수정해야 하는지 구체적으로 작성하세요.

출력은 JSON 객체 하나만 반환합니다.

반환 형식:

{
  "title": "챕터 제목",
  "editorial_brief": "전체 수정 방향",
  "structure_changes": [
    {
      "location": "수정 위치",
      "action": "move | add | remove | merge | split | rewrite",
      "instruction": "구체적인 지시",
      "reason": "수정 이유"
    }
  ],
  "style_changes": [
    {
      "location": "수정 위치",
      "instruction": "문체 수정 지시"
    }
  ],
  "content_changes": [
    {
      "location": "수정 위치",
      "instruction": "내용 수정 지시"
    }
  ],
  "fact_check_items": [
    {
      "claim": "확인할 주장",
      "instruction": "확인 또는 처리 방법"
    }
  ],
  "must_preserve": [
    "유지해야 할 내용"
  ]
}
""".strip()


def build_editor_user_prompt(
    *,
    draft: dict[str, Any],
    review: dict[str, Any],
) -> str:
    input_data = {
        "chapter_draft": draft,
        "review_report": review,
    }

    return (
        "아래 초안과 검토 결과를 바탕으로 편집 지시서를 작성하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
