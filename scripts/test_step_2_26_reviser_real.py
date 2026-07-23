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
            "Google ADK의 Agent 구조를 학습하는 기술 교재"
        ),
        "target_reader": (
            "Python 기본 문법을 아는 ADK 입문자"
        ),
        "book_style": (
            "개념 설명과 실습을 결합한 기술 교재"
        ),
        "goal": (
            "독자가 ADK Agent, Tool, Session의 역할을 "
            "구분하고 간단한 Agent를 구현하게 한다."
        ),
        "book_type": "programming",
        "writing_guidelines": [
            "처음 등장하는 용어를 쉽게 설명한다.",
            "근거 없는 기능 설명을 하지 않는다.",
            "개념 설명 뒤에 간단한 예시를 제공한다.",
        ],
    }

    chapter_plan = {
        "chapter_id": "chapter-01",
        "title": "ADK와 AI Agent의 기본 개념",
        "description": (
            "일반 LLM 호출과 Agent의 차이 및 "
            "ADK 핵심 요소를 설명한다."
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

    research_artifact = {
        "artifact_type": "RESEARCH_ARTIFACT",
        "chapter_id": "chapter-01",
        "title": "ADK와 AI Agent의 기본 개념",
        "research_summary": (
            "ADK는 Agent, Runner, Session, Tool을 이용해 "
            "Agent 애플리케이션을 구성하는 프레임워크이다."
        ),
        "findings": [
            {
                "topic": "ADK 구성요소",
                "content": (
                    "Agent는 모델과 instruction, tool을 조합하고, "
                    "Runner는 실행을 담당하며 Session은 상태를 유지한다."
                ),
                "importance": "high",
                "source_ids": [
                    "source-adk-overview"
                ],
                "is_inference": False,
            },
            {
                "topic": "Agent와 일반 LLM 호출의 차이",
                "content": (
                    "Agent는 필요한 도구를 선택하고 도구 실행 결과를 "
                    "다음 처리에 활용할 수 있다."
                ),
                "importance": "high",
                "source_ids": [
                    "source-adk-agent"
                ],
                "is_inference": False,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Session은 대화 상태를 유지하는 데 사용된다."
                ),
                "support": (
                    "제공 자료에서 Session은 대화 상태를 "
                    "구분하고 유지한다고 설명한다."
                ),
                "source_id": "source-adk-overview",
                "confidence": "high",
            }
        ],
        "writing_guidance": [
            "일반 LLM 호출과 Agent를 비교해 설명한다.",
            "각 ADK 구성요소의 책임을 분리해 설명한다.",
        ],
        "required_sections": (
            chapter_plan["required_sections"]
        ),
        "gaps": [
            "Runner의 내부 실행 과정은 자료에서 확인되지 않는다."
        ],
        "source_ids": [
            "source-adk-overview",
            "source-adk-agent",
        ],
        "metadata": {},
    }

    chapter_draft = {
        "artifact_type": "CHAPTER_DRAFT",
        "chapter_id": "chapter-01",
        "title": "ADK와 AI Agent의 기본 개념",
        "summary": (
            "ADK와 AI Agent의 핵심 개념을 설명한다."
        ),
        "markdown": """
# ADK와 AI Agent의 기본 개념

## AI Agent란 무엇인가

AI Agent는 사용자의 요청을 받고 스스로 모든 문제를 해결하는
인공지능 프로그램이다. 일반 LLM과 달리 Agent는 외부 도구를
사용할 수 있다.

## 일반 LLM 호출과의 차이

일반 LLM 호출은 질문을 입력하면 텍스트 답변을 생성한다.
Agent는 필요한 도구를 선택하고 도구 실행 결과를 다음 응답에
사용할 수 있다.

## ADK의 핵심 구성요소

ADK는 Agent, Runner, Session, Tool로 구성된다.

Agent는 모델과 instruction, tool을 조합한다. Runner는 Agent를
실행한다. Session은 대화 상태를 구분하고 유지한다. Tool은 외부
데이터를 조회하거나 실제 작업을 실행한다.

## 마무리

ADK를 사용하면 모든 AI 업무를 완전히 자동화할 수 있다.
""".strip(),
        "key_points": chapter_plan["key_points"],
        "source_ids": [
            "source-adk-overview",
            "source-adk-agent",
        ],
        "metadata": {
            "role": "writer",
            "revision": 0,
        },
    }

    review_artifact = {
        "artifact_type": "REVIEW_ARTIFACT",
        "chapter_id": "chapter-01",
        "title": "ADK와 AI Agent의 기본 개념",
        "overall_score": 75,
        "verdict": "minor_revision",
        "review_summary": (
            "초안은 기본 개념을 포함하지만 Agent 정의가 과장되어 있고, "
            "필수 섹션인 간단한 실행 흐름이 빠져 있다."
        ),
        "strengths": [
            "일반 LLM과 Agent의 차이를 설명했다.",
            "ADK의 핵심 구성요소를 포함했다.",
        ],
        "issues": [
            {
                "category": "accuracy",
                "severity": "major",
                "location": "AI Agent란 무엇인가",
                "description": (
                    "'모든 문제를 해결한다'는 표현은 과장되어 있다."
                ),
                "recommendation": (
                    "목표를 달성하기 위해 모델과 도구를 활용하는 "
                    "구조라는 설명으로 수정한다."
                ),
                "source_ids": [
                    "source-adk-agent"
                ],
            },
            {
                "category": "completeness",
                "severity": "major",
                "location": "전체 구조",
                "description": (
                    "필수 섹션인 간단한 실행 흐름이 없다."
                ),
                "recommendation": (
                    "사용자 요청부터 Agent, Tool, Session을 거치는 "
                    "간단한 실행 흐름을 추가한다."
                ),
                "source_ids": [
                    "source-adk-overview"
                ],
            },
            {
                "category": "evidence",
                "severity": "minor",
                "location": "마무리",
                "description": (
                    "모든 AI 업무를 완전히 자동화할 수 있다는 "
                    "주장에 근거가 없다."
                ),
                "recommendation": (
                    "해당 문장을 삭제하고 ADK의 역할을 제한적으로 "
                    "요약한다."
                ),
                "source_ids": [],
            },
        ],
        "revision_instructions": [
            "Agent 정의에서 '모든 문제를 해결한다'는 표현을 제거한다.",
            "Agent가 목표를 달성하기 위해 모델과 도구를 활용한다고 설명한다.",
            "'간단한 실행 흐름' 섹션을 추가한다.",
            "Runner의 역할을 한 문장 이상으로 구체화한다.",
            "근거 없는 완전 자동화 주장을 제거한다.",
        ],
        "fact_check_items": [
            {
                "claim": (
                    "AI Agent는 모든 문제를 해결할 수 있다."
                ),
                "status": "unsupported",
                "explanation": (
                    "제공 자료에서 지원하지 않는 과장된 주장이다."
                ),
                "source_ids": [],
            },
            {
                "claim": (
                    "Session은 대화 상태를 유지한다."
                ),
                "status": "supported",
                "explanation": (
                    "Research Artifact의 근거와 일치한다."
                ),
                "source_ids": [
                    "source-adk-overview"
                ],
            },
        ],
        "missing_sections": [
            "간단한 실행 흐름"
        ],
        "source_ids": [
            "source-adk-overview",
            "source-adk-agent",
        ],
        "metadata": {
            "role": "reviewer",
        },
    }

    print("=" * 72)
    print("STEP 2-26-4 REVISER REAL TEST")
    print("=" * 72)

    result = await service.revise_chapter(
        book_config=book_config,
        chapter_plan=chapter_plan,
        research_artifact=research_artifact,
        chapter_draft=chapter_draft,
        review_artifact=review_artifact,
        previous_chapters=[],
        revision_number=1,
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
        "CHAPTER_DRAFT"
    )

    assert result["chapter_id"] == "chapter-01"

    assert result["markdown"].startswith("# ")

    assert len(result["markdown"]) >= 300

    assert "간단한 실행 흐름" in result["markdown"]

    assert (
        "모든 AI 업무를 완전히 자동화"
        not in result["markdown"]
    )

    metadata = result.get("metadata", {})

    assert metadata.get("role") == "reviser"
    assert metadata.get("stage") == "reviser"
    assert metadata.get("revision") == 1
    assert metadata.get("based_on_review") is True

    print(
        "artifact_type=",
        result["artifact_type"],
    )
    print(
        "chapter_id=",
        result["chapter_id"],
    )
    print(
        "title=",
        result["title"],
    )
    print(
        "markdown_length=",
        len(result["markdown"]),
    )
    print(
        "role=",
        metadata.get("role"),
    )
    print(
        "revision=",
        metadata.get("revision"),
    )
    print(
        "review_verdict=",
        metadata.get("review_verdict"),
    )
    print(
        "model=",
        metadata.get("model"),
    )
    print(
        "done_reason=",
        metadata.get("done_reason"),
    )

    print()
    print("PASS: Reviser model routing")
    print("PASS: Markdown text generation")
    print("PASS: Review instructions applied")
    print("PASS: CHAPTER_DRAFT validation")
    print("PASS: Reviser metadata")
    print()
    print("PASS: STEP 2-26-4")


if __name__ == "__main__":
    asyncio.run(main())
