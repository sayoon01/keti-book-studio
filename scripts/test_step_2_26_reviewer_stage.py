from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from backend.orchestration.stages.reviewer_stage import (
    ReviewerStage,
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

    stage = ReviewerStage()

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
            "chapter_id": "chapter-review-stage",
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
            "chapter_id": "chapter-review-stage",
            "title": "Generation과 Orchestration 분리",
            "research_summary": (
                "Generation은 생성 책임, Orchestration은 "
                "실행 순서 책임을 담당한다."
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
                "계층별 책임을 비교한다."
            ],
            "required_sections": [
                "Generation",
                "Orchestration",
                "Infrastructure",
                "호출 흐름",
            ],
            "gaps": [],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {},
        },
        "chapter_draft": {
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": "chapter-review-stage",
            "title": "Generation과 Orchestration 분리",
            "summary": (
                "Book Studio의 계층 분리를 설명한다."
            ),
            "markdown": """
# Generation과 Orchestration 분리

## Generation

Generation은 프롬프트를 생성하고 역할별 모델을 선택한다.
또한 LLM 결과를 Artifact 구조로 검증한다.

## Orchestration

Orchestration은 Researcher, Writer, Reviewer Stage의 실행 순서를
관리하고 이전 Stage의 Artifact를 다음 Stage로 전달한다.

## 결론

두 계층을 분리하면 LLM 생성 로직과 실행 순서 로직을 독립적으로
변경할 수 있다.
""".strip(),
            "key_points": [
                "Generation 책임",
                "Orchestration 책임",
            ],
            "source_ids": [
                "source-architecture"
            ],
            "metadata": {},
        },
        "previous_chapters": [],
    }

    result = await stage.execute(context)

    assert result["last_stage"] == "reviewer"
    assert "review" in result
    assert "review_artifact" in result
    assert "artifacts" in result
    assert "review" in result["artifacts"]

    review = result["review_artifact"]

    assert review["artifact_type"] == (
        "REVIEW_ARTIFACT"
    )

    assert review["chapter_id"] == (
        "chapter-review-stage"
    )

    print("=" * 72)
    print("STEP 2-26-3 REVIEWER STAGE TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        review["artifact_type"],
    )
    print(
        "chapter_id=",
        review["chapter_id"],
    )
    print(
        "overall_score=",
        review["overall_score"],
    )
    print(
        "verdict=",
        review["verdict"],
    )
    print(
        "issues=",
        len(review["issues"]),
    )
    print(
        "last_stage=",
        result["last_stage"],
    )
    print()
    print("PASS: ReviewerStage")
    print("PASS: Stage → Generation Service")
    print("PASS: Review Artifact handoff")


if __name__ == "__main__":
    asyncio.run(main())
