from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from backend.orchestration.stages.editor_stage import (
    EditorStage,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)


async def main() -> None:
    load_dotenv()

    markdown = """
# Generation과 Orchestration

## Generation

Generation은 프롬프트와 모델 실행을 담당한다.

## Orchestration

Orchestration은 Stage의 실행 순서를 관리한다.
""".strip()

    selected_text = (
        "Generation은 프롬프트와 모델 실행을 담당한다."
    )

    start = markdown.index(selected_text)
    end = start + len(selected_text)

    current_draft = {
        "artifact_type": "CHAPTER_DRAFT",
        "chapter_id": "chapter-editor-stage",
        "title": "Generation과 Orchestration",
        "summary": (
            "Generation과 Orchestration의 책임을 설명한다."
        ),
        "markdown": markdown,
        "key_points": [
            "Generation",
            "Orchestration",
        ],
        "source_ids": [
            "source-architecture"
        ],
        "metadata": {
            "role": "reviser",
            "revision": 1,
        },
    }

    context = {
        "book_config": {
            "title": "Book Studio 구조 설계",
            "language": "ko",
            "target_reader": "AI 시스템 개발자",
            "book_style": "기술서",
            "goal": (
                "Book Studio 계층 구조를 이해한다."
            ),
        },
        "chapter_plan": {
            "chapter_id": "chapter-editor-stage",
            "title": "Generation과 Orchestration",
            "key_points": [
                "Generation",
                "Orchestration",
            ],
        },
        "chapter_draft": current_draft,
        "research_artifact": {
            "artifact_type": "RESEARCH_ARTIFACT",
            "chapter_id": "chapter-editor-stage",
            "research_summary": (
                "Generation은 프롬프트 구성, 모델 호출, "
                "결과 검증을 담당한다."
            ),
            "findings": [],
            "evidence": [],
            "writing_guidance": [],
            "required_sections": [],
            "gaps": [],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {},
        },
        "editor_command": {
            "mode": "expand",
            "scope": "selection",
            "instruction": (
                "Generation의 책임을 두 문장으로 "
                "조금 더 구체적으로 작성하세요."
            ),
            "selection": {
                "start": start,
                "end": end,
                "text": selected_text,
            },
        },
        "previous_chapters": [],
    }

    stage = EditorStage()

    result = await stage.execute(context)

    assert result["last_stage"] == "editor"

    assert "edited_draft" in result

    edited_draft = result["edited_draft"]

    assert edited_draft["artifact_type"] == (
        "CHAPTER_DRAFT"
    )

    assert edited_draft["chapter_id"] == (
        "chapter-editor-stage"
    )

    assert result["chapter_draft"] == (
        edited_draft
    )

    assert result["draft"] == edited_draft

    assert result["artifacts"]["editor"] == (
        edited_draft
    )

    assert len(result["edit_history"]) == 1

    assert (
        result["edit_history"][0]["before"]
        == current_draft
    )

    metadata = edited_draft["metadata"]

    assert metadata["role"] == "editor"
    assert metadata["revision"] == 2
    assert metadata["edit_scope"] == "selection"

    print("=" * 72)
    print("STEP 2-26-5 EDITOR STAGE TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        edited_draft["artifact_type"],
    )
    print(
        "chapter_id=",
        edited_draft["chapter_id"],
    )
    print(
        "revision=",
        metadata["revision"],
    )
    print(
        "edit_mode=",
        metadata["edit_mode"],
    )
    print(
        "edit_scope=",
        metadata["edit_scope"],
    )
    print(
        "edit_history=",
        len(result["edit_history"]),
    )
    print(
        "current_draft_is_edited=",
        result["chapter_draft"]
        == edited_draft,
    )
    print(
        "last_stage=",
        result["last_stage"],
    )
    print()
    print("PASS: EditorStage")
    print("PASS: Stage → Generation Service")
    print("PASS: Current draft resolution")
    print("PASS: Edit history preservation")
    print("PASS: Edited draft handoff")


if __name__ == "__main__":
    asyncio.run(main())
