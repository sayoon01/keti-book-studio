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

    book_config = {
        "title": "ADK 입문부터 중급까지",
        "language": "ko",
        "description": (
            "Google ADK를 처음 접하는 개발자가 "
            "에이전트 구조와 도구 연동을 학습하는 교재"
        ),
        "target_reader": (
            "Python 기본 문법을 알고 있지만 "
            "AI Agent 프레임워크는 처음인 개발자"
        ),
        "book_style": "개념 설명과 실습을 결합한 기술 교재",
        "goal": (
            "ADK의 Agent, Tool, Session, Memory 구조를 "
            "이해하고 직접 구현할 수 있게 한다."
        ),
        "book_type": "programming",
        "writing_guidelines": [
            "처음 등장하는 용어는 쉽게 설명한다.",
            "개념 설명 뒤에 짧은 코드 예제를 제공한다.",
            "근거 없는 기능 설명은 하지 않는다.",
        ],
    }

    chapter_plan = {
        "chapter_id": "chapter-01",
        "title": "ADK와 AI Agent의 기본 개념",
        "description": (
            "AI Agent와 일반적인 LLM 호출의 차이를 설명하고, "
            "ADK의 핵심 구성요소를 소개한다."
        ),
        "goal": (
            "독자가 Agent, Tool, Session의 역할을 "
            "구분할 수 있게 한다."
        ),
        "key_points": [
            "일반 LLM 호출과 Agent의 차이",
            "Agent의 목표 기반 실행",
            "Tool의 역할",
            "Session과 상태 관리",
        ],
        "required_sections": [
            "AI Agent란 무엇인가",
            "일반 LLM 호출과의 차이",
            "ADK의 핵심 구성요소",
            "간단한 실행 흐름",
        ],
        "source_ids": [
            "source-adk-overview",
            "source-adk-agent",
        ],
        "target_length": 3000,
    }

    sources = [
        {
            "source_id": "source-adk-overview",
            "title": "ADK 개요",
            "type": "markdown",
            "content": (
                "ADK는 AI Agent 애플리케이션을 구성하기 위한 "
                "개발 프레임워크다. Agent는 모델과 instruction, "
                "tool 등을 조합해 사용자 요청을 처리한다. "
                "Runner는 Agent 실행을 담당하며 Session은 "
                "대화 상태를 구분하고 유지하는 데 사용된다."
            ),
        },
        {
            "source_id": "source-adk-agent",
            "title": "Agent와 Tool",
            "type": "markdown",
            "content": (
                "일반적인 LLM 호출은 입력에 대한 텍스트 응답을 "
                "생성하는 데 집중한다. Agent 구조에서는 모델이 "
                "도구 사용 여부를 판단하고, 도구 실행 결과를 "
                "활용해 다음 응답을 생성할 수 있다. Tool은 외부 "
                "데이터 조회나 실제 작업 실행을 담당한다."
            ),
        },
    ]

    print("=" * 72)
    print("STEP 2-26-2 RESEARCHER REAL TEST")
    print("=" * 72)

    result = await service.research_chapter(
        book_config=book_config,
        chapter_plan=chapter_plan,
        sources=sources,
        previous_chapters=[],
    )

    print()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)

    assert result["artifact_type"] == (
        "RESEARCH_ARTIFACT"
    )

    assert result["chapter_id"] == "chapter-01"

    assert result["title"]

    assert len(result["research_summary"]) >= 20

    assert isinstance(result["findings"], list)
    assert len(result["findings"]) >= 1

    assert isinstance(
        result["writing_guidance"],
        list,
    )
    assert len(result["writing_guidance"]) >= 1

    assert isinstance(result["source_ids"], list)

    metadata = result.get("metadata", {})

    assert metadata.get("model") == "qwen3:32b"
    assert metadata.get("role") == "researcher"
    assert metadata.get("response_format") == "json"

    assert "summary" not in result
    assert "key_points" not in result

    print(
        "artifact_type=",
        result["artifact_type"],
    )

    print(
        "chapter_id=",
        result["chapter_id"],
    )

    print(
        "model=",
        metadata.get("model"),
    )

    print(
        "response_format=",
        metadata.get("response_format"),
    )

    print(
        "done_reason=",
        metadata.get("done_reason"),
    )

    print(
        "findings=",
        len(result["findings"]),
    )

    print(
        "evidence=",
        len(result["evidence"]),
    )

    print(
        "source_ids=",
        result["source_ids"],
    )

    print(
        "canonical_fields_only=",
        (
            "summary" not in result
            and "key_points" not in result
        ),
    )

    print()
    print("PASS: Researcher model routing")
    print("PASS: JSON structured generation")
    print("PASS: Research Artifact validation")
    print("PASS: Research metadata")
    print("PASS: Canonical Research Artifact fields")
    print()
    print("PASS: STEP 2-26-2")


if __name__ == "__main__":
    asyncio.run(main())
