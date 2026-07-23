from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from backend.orchestration.stages.reviser_stage import (
    ReviserStage,
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

    stage = ReviserStage()

    context = {
        "book_config": {
            "title": "Book Studio 구조 설계",
            "language": "ko",
            "target_reader": "AI 시스템 개발자",
            "book_style": "기술서",
            "goal": (
                "Generation과 Orchestration의 책임을 이해한다."
            ),
            "book_type": "system_design",
        },
        "chapter_plan": {
            "chapter_id": "chapter-reviser-stage",
            "title": "Generation과 Orchestration 분리",
            "description": (
                "두 계층을 분리하는 이유를 설명한다."
            ),
            "goal": (
                "독자가 각 계층의 책임을 구분하게 한다."
            ),
            "key_points": [
                "Generation 책임",
                "Orchestration 책임",
                "Infrastructure 책임",
            ],
            "required_sections": [
                "Generation",
                "Orchestration",
                "Infrastructure",
                "호출 흐름",
            ],
            "source_ids": [
                "source-architecture"
            ],
        },
        "research_artifact": {
            "artifact_type": "RESEARCH_ARTIFACT",
            "chapter_id": "chapter-reviser-stage",
            "title": "Generation과 Orchestration 분리",
            "research_summary": (
                "Generation은 생성 책임을, Orchestration은 "
                "실행 순서와 Artifact 전달 책임을 담당한다."
            ),
            "findings": [
                {
                    "topic": "Generation 책임",
                    "content": (
                        "Generation은 프롬프트, 모델 라우팅, "
                        "결과 검증을 담당한다."
                    ),
                    "importance": "high",
                    "source_ids": [
                        "source-architecture"
                    ],
                    "is_inference": False,
                },
                {
                    "topic": "Orchestration 책임",
                    "content": (
                        "Orchestration은 Stage 순서와 "
                        "Artifact 전달을 담당한다."
                    ),
                    "importance": "high",
                    "source_ids": [
                        "source-architecture"
                    ],
                    "is_inference": False,
                },
            ],
            "evidence": [],
            "writing_guidance": [
                "각 계층의 책임을 비교한다."
            ],
            "required_sections": [
                "Generation",
                "Orchestration",
                "Infrastructure",
                "호출 흐름",
            ],
            "gaps": [
                "Infrastructure 설명은 추가 정리가 필요하다."
            ],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {},
        },
        "chapter_draft": {
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": "chapter-reviser-stage",
            "title": "Generation과 Orchestration 분리",
            "summary": (
                "Book Studio의 계층 분리를 설명한다."
            ),
            "markdown": """
# Generation과 Orchestration 분리

## Generation

Generation은 프롬프트를 생성하고 모델을 선택한다.

## Orchestration

Orchestration은 Stage의 실행 순서를 관리한다.

## 결론

두 계층을 분리하면 좋다.
""".strip(),
            "key_points": [
                "Generation 책임",
                "Orchestration 책임",
            ],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {
                "role": "writer",
                "revision": 0,
            },
        },
        "review_artifact": {
            "artifact_type": "REVIEW_ARTIFACT",
            "chapter_id": "chapter-reviser-stage",
            "title": "Generation과 Orchestration 분리",
            "overall_score": 65,
            "verdict": "major_revision",
            "review_summary": (
                "Generation과 Orchestration의 기본 설명은 있으나 "
                "Infrastructure와 호출 흐름이 빠져 있다."
            ),
            "strengths": [
                "두 계층을 구분해 설명했다."
            ],
            "issues": [
                {
                    "category": "completeness",
                    "severity": "major",
                    "location": "전체 구조",
                    "description": (
                        "Infrastructure 섹션과 호출 흐름이 빠져 있다."
                    ),
                    "recommendation": (
                        "Infrastructure 책임과 전체 호출 흐름을 추가한다."
                    ),
                    "source_ids": [
                        "source-architecture"
                    ],
                }
            ],
            "revision_instructions": [
                "Infrastructure 섹션을 추가한다.",
                "Stage부터 LLM Client까지 호출 흐름을 설명한다.",
                "각 계층의 책임을 명확하게 구분한다.",
                "결론을 구체적으로 작성한다.",
            ],
            "fact_check_items": [],
            "missing_sections": [
                "Infrastructure",
                "호출 흐름",
            ],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {
                "role": "reviewer",
            },
        },
        "previous_chapters": [],
    }

    original_draft = context["chapter_draft"]

    result = await stage.execute(context)

    assert result["last_stage"] == "reviser"

    assert "original_draft" in result
    assert "revised_draft" in result

    assert result["original_draft"] == (
        original_draft
    )

    revised_draft = result["revised_draft"]

    assert revised_draft["artifact_type"] == (
        "CHAPTER_DRAFT"
    )

    assert revised_draft["chapter_id"] == (
        "chapter-reviser-stage"
    )

    assert result["chapter_draft"] == (
        revised_draft
    )

    assert result["draft"] == revised_draft

    assert result["artifacts"]["reviser"] == (
        revised_draft
    )

    assert revised_draft["metadata"]["role"] == (
        "reviser"
    )

    assert revised_draft["metadata"]["revision"] == 1

    print("=" * 72)
    print("STEP 2-26-4 REVISER STAGE TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        revised_draft["artifact_type"],
    )
    print(
        "chapter_id=",
        revised_draft["chapter_id"],
    )
    print(
        "revision=",
        revised_draft["metadata"]["revision"],
    )
    print(
        "markdown_length=",
        len(revised_draft["markdown"]),
    )
    print(
        "original_draft_preserved=",
        result["original_draft"] == original_draft,
    )
    print(
        "current_draft_is_revised=",
        result["chapter_draft"] == revised_draft,
    )
    print(
        "last_stage=",
        result["last_stage"],
    )
    print()
    print("PASS: ReviserStage")
    print("PASS: Stage → Generation Service")
    print("PASS: Original draft preservation")
    print("PASS: Revised draft handoff")
    print("PASS: Current draft replacement")


if __name__ == "__main__":
    asyncio.run(main())
