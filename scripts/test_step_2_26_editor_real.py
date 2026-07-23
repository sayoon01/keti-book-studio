from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from backend.generation import (
    ChapterGenerationService,
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

    service = ChapterGenerationService()

    markdown = """
# ADK와 AI Agent의 기본 개념

## AI Agent란 무엇인가

AI Agent는 사용자가 제시한 목표를 달성하기 위해 모델과
외부 도구를 활용하는 인공지능 시스템입니다.

## 일반 LLM 호출과의 차이

일반 LLM 호출은 입력에 대한 텍스트 응답을 생성합니다.
Agent는 요청을 분석한 뒤 필요한 도구를 선택할 수 있습니다.

## ADK의 핵심 구성요소

ADK는 Agent, Runner, Session, Tool로 구성됩니다.

Agent는 모델과 Instruction, Tool을 조합합니다.
Runner는 Agent를 실행합니다.
Session은 대화 상태를 유지합니다.
Tool은 외부 데이터 조회나 작업 실행을 담당합니다.
""".strip()

    selected_text = (
        "Runner는 Agent를 실행합니다."
    )

    selection_start = markdown.index(
        selected_text
    )

    selection_end = (
        selection_start
        + len(selected_text)
    )

    result = await service.edit_chapter(
        book_config={
            "title": "ADK 입문부터 중급까지",
            "language": "ko",
            "target_reader": "ADK 입문 개발자",
            "book_style": "실습형 기술 교재",
            "goal": (
                "독자가 ADK의 핵심 구조를 이해하게 한다."
            ),
            "writing_guidelines": [
                "용어를 쉽게 설명한다.",
                "근거 없는 기능을 추가하지 않는다.",
            ],
        },
        chapter_plan={
            "chapter_id": "chapter-editor-real",
            "title": "ADK와 AI Agent의 기본 개념",
            "goal": (
                "Agent, Runner, Session, Tool의 "
                "역할을 구분한다."
            ),
            "key_points": [
                "Agent",
                "Runner",
                "Session",
                "Tool",
            ],
            "required_sections": [
                "AI Agent란 무엇인가",
                "일반 LLM 호출과의 차이",
                "ADK의 핵심 구성요소",
            ],
        },
        chapter_draft={
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": "chapter-editor-real",
            "title": "ADK와 AI Agent의 기본 개념",
            "summary": (
                "ADK와 AI Agent의 기본 구조를 설명한다."
            ),
            "markdown": markdown,
            "key_points": [
                "Agent",
                "Runner",
                "Session",
                "Tool",
            ],
            "source_ids": [
                "source-adk-overview",
            ],
            "metadata": {
                "role": "reviser",
                "revision": 1,
            },
        },
        editor_command={
            "mode": "expand",
            "scope": "selection",
            "instruction": (
                "Runner가 사용자 입력을 받아 Agent 실행 흐름을 "
                "관리한다는 내용을 두 문장 정도로 설명하세요."
            ),
            "selection": {
                "start": selection_start,
                "end": selection_end,
                "text": selected_text,
            },
        },
        research_artifact={
            "artifact_type": "RESEARCH_ARTIFACT",
            "chapter_id": "chapter-editor-real",
            "research_summary": (
                "Runner는 Agent 실행과 실행 흐름 관리를 담당한다."
            ),
            "findings": [
                {
                    "topic": "Runner",
                    "content": (
                        "Runner는 사용자의 요청을 받아 "
                        "Agent 실행을 시작하고 실행 흐름을 관리한다."
                    ),
                    "importance": "high",
                    "source_ids": [
                        "source-adk-overview"
                    ],
                    "is_inference": False,
                }
            ],
            "evidence": [],
            "writing_guidance": [],
            "required_sections": [],
            "gaps": [],
            "source_ids": [
                "source-adk-overview"
            ],
            "metadata": {},
        },
        previous_chapters=[],
        revision_number=2,
    )

    print("=" * 72)
    print("STEP 2-26-5 EDITOR REAL TEST")
    print("=" * 72)
    print()

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    metadata = result["metadata"]

    assert result["artifact_type"] == (
        "CHAPTER_DRAFT"
    )

    assert result["chapter_id"] == (
        "chapter-editor-real"
    )

    assert result["markdown"].startswith("# ")

    assert len(result["markdown"]) > len(
        markdown
    )

    assert selected_text not in result["markdown"]

    assert metadata["role"] == "editor"
    assert metadata["stage"] == "editor"
    assert metadata["revision"] == 2
    assert metadata["edit_mode"] == "expand"
    assert metadata["edit_scope"] == "selection"

    print()
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)
    print(
        "artifact_type=",
        result["artifact_type"],
    )
    print(
        "chapter_id=",
        result["chapter_id"],
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
        "model=",
        metadata["model"],
    )
    print(
        "markdown_length=",
        len(result["markdown"]),
    )
    print()
    print("PASS: Editor model routing")
    print("PASS: Selection edit generation")
    print("PASS: Selection replacement")
    print("PASS: CHAPTER_DRAFT validation")
    print("PASS: Editor metadata")
    print()
    print("PASS: STEP 2-26-5")


if __name__ == "__main__":
    asyncio.run(main())
