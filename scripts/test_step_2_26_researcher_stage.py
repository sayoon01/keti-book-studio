from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from backend.orchestration.stages.researcher_stage import (
    ResearcherStage,
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

    stage = ResearcherStage()

    context = {
        "book_config": {
            "title": "Book Studio 구조 설계",
            "language": "ko",
            "target_reader": "AI 시스템 개발자",
            "book_style": "기술서",
            "goal": (
                "Book Studio의 레이어 구조를 이해한다."
            ),
            "book_type": "system_design",
        },
        "chapter_plan": {
            "chapter_id": "chapter-stage-test",
            "title": "Generation과 Orchestration 분리",
            "description": (
                "생성 계층과 실행 흐름 계층을 "
                "분리해야 하는 이유를 설명한다."
            ),
            "key_points": [
                "Generation 책임",
                "Orchestration 책임",
                "Infrastructure 책임",
            ],
            "required_sections": [
                "레이어별 책임",
                "호출 흐름",
                "분리의 장점",
            ],
            "source_ids": [
                "source-architecture",
            ],
        },
        "sources": [
            {
                "source_id": "source-architecture",
                "title": "Book Studio Architecture",
                "type": "markdown",
                "content": (
                    "Orchestration은 Stage 실행 순서를 담당한다. "
                    "Generation은 프롬프트, 모델 라우팅, 결과 검증을 "
                    "담당한다. Infrastructure는 Ollama HTTP 통신을 "
                    "담당한다."
                ),
            }
        ],
        "previous_chapters": [],
    }

    result = await stage.execute(context)

    assert result["last_stage"] == "researcher"
    assert "research" in result
    assert "research_artifact" in result
    assert "artifacts" in result
    assert "research" in result["artifacts"]

    research = result["research"]

    assert research["artifact_type"] == (
        "RESEARCH_ARTIFACT"
    )

    assert research["chapter_id"] == (
        "chapter-stage-test"
    )

    print("=" * 72)
    print("STEP 2-26-2 RESEARCHER STAGE TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        research["artifact_type"],
    )
    print(
        "chapter_id=",
        research["chapter_id"],
    )
    print(
        "findings=",
        len(research["findings"]),
    )
    print(
        "last_stage=",
        result["last_stage"],
    )
    print()
    print("PASS: ResearcherStage")
    print("PASS: Stage → Generation Service")
    print("PASS: Context artifact handoff")


if __name__ == "__main__":
    asyncio.run(main())
