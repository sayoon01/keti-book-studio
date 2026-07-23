from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.generation.chapter_generation_service import (
    ChapterGenerationService,
)


CHAPTER_PLAN = {
    "chapter_id": "chapter-01",
    "unit_id": "unit-01",
    "title": "AI 에이전트의 기본 개념",
    "description": (
        "AI 에이전트가 무엇이며 일반적인 LLM 호출과 "
        "어떤 차이가 있는지 단계적으로 설명한다."
    ),
    "objectives": [
        "AI 에이전트의 정의를 이해한다.",
        "모델, 도구, 상태의 관계를 이해한다.",
        "일반 LLM 호출과 에이전트 실행을 구분한다.",
    ],
    "sections": [
        {
            "title": "AI 에이전트란 무엇인가",
            "description": (
                "목표를 받아 판단하고 행동하는 "
                "시스템으로서의 에이전트를 설명한다."
            ),
        },
        {
            "title": "에이전트의 핵심 구성요소",
            "description": (
                "모델, 도구, 상태, 실행 흐름의 "
                "관계를 설명한다."
            ),
        },
        {
            "title": "일반 LLM 호출과의 차이",
            "description": (
                "한 번의 텍스트 생성과 반복적인 "
                "판단 및 행동 과정을 비교한다."
            ),
        },
    ],
    "required_points": [
        "에이전트는 목표를 중심으로 동작한다.",
        "도구를 통해 외부 시스템과 상호작용할 수 있다.",
        "상태와 실행 기록을 관리해야 한다.",
    ],
    "target_length": 1800,
    "source_ids": [
        "test-source-001",
    ],
}


RESEARCH = {
    "summary": (
        "AI 에이전트는 대규모 언어 모델을 추론 엔진으로 "
        "활용하면서 도구, 상태, 실행 제어를 결합한 시스템이다."
    ),
    "key_points": [
        (
            "일반적인 LLM 호출은 입력에 대한 출력을 "
            "한 번 생성하는 형태가 많다."
        ),
        (
            "에이전트는 목표를 달성하기 위해 여러 단계를 "
            "계획하고 도구를 사용할 수 있다."
        ),
        (
            "실제 서비스에서는 세션, 상태, 오류 처리, "
            "재시도, 실행 기록이 필요하다."
        ),
    ],
    "facts": [
        {
            "statement": (
                "에이전트 시스템은 모델 호출 외에 "
                "도구 실행과 상태 관리를 포함할 수 있다."
            ),
            "source_id": "test-source-001",
        }
    ],
    "evidence": [
        {
            "source_id": "test-source-001",
            "content": (
                "테스트용 내부 자료에서는 AI 에이전트의 "
                "구성요소를 모델, 도구, 상태, 실행 흐름으로 정의한다."
            ),
        }
    ],
    "source_ids": [
        "test-source-001",
    ],
    "limitations": [
        (
            "실제 프레임워크마다 구현 방식이 다르므로 "
            "공통 개념을 중심으로 설명해야 한다."
        )
    ],
}


BOOK_CONTEXT = {
    "title": "ADK 입문부터 중급까지",
    "description": (
        "AI Agent와 Google ADK의 핵심 개념을 "
        "단계적으로 학습하는 실습형 교재"
    ),
    "target_reader": (
        "Python 기본 문법을 알고 있지만 "
        "AI 에이전트 프레임워크는 처음인 개발자"
    ),
    "book_style": (
        "개념 설명과 실제 예시를 함께 제공하는 실습형 교재"
    ),
    "goal": (
        "독자가 AI 에이전트의 기본 구조를 이해하고 "
        "간단한 시스템을 설계할 수 있게 한다."
    ),
    "language": "ko",
}


async def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )

    service = ChapterGenerationService()

    try:
        result = await service.write_chapter(
            chapter_plan=CHAPTER_PLAN,
            research=RESEARCH,
            book_context=BOOK_CONTEXT,
        )

    except Exception as exc:
        print("\n" + "=" * 70)
        print("STEP 2-25 FAILED")
        print("=" * 70)
        print(f"type={type(exc).__name__}")
        print(f"message={exc}")
        print()

        traceback.print_exc()
        sys.exit(1)

    generation = result["_generation"]

    print("\n" + "=" * 70)
    print("STEP 2-25 RESULT")
    print("=" * 70)

    print(f"title={result['title']}")
    print(f"summary={result['summary']}")
    print(
        "markdown_length="
        f"{len(result['markdown'])}"
    )
    print(
        "key_points_count="
        f"{len(result['key_points'])}"
    )
    print(
        "source_ids="
        f"{result['source_ids']}"
    )

    print("\n" + "=" * 70)
    print("GENERATION METADATA")
    print("=" * 70)

    print(
        json.dumps(
            generation,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n" + "=" * 70)
    print("MARKDOWN PREVIEW")
    print("=" * 70)

    print(result["markdown"][:1500])

    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)

    assert generation["model"] == "gemma4:31b", (
        "Writer 모델이 gemma4:31b가 아닙니다. "
        f"actual={generation['model']}"
    )

    assert generation["response_format"] == "markdown", (
        "Writer가 Markdown 모드로 실행되지 않았습니다."
    )

    assert generation["done_reason"] in (
        "stop",
        None,
    ), (
        "비정상 done_reason입니다. "
        f"actual={generation['done_reason']}"
    )

    assert len(result["markdown"]) >= 300, (
        "Markdown 본문이 너무 짧습니다."
    )

    assert result["markdown"].lstrip().startswith("#"), (
        "Markdown이 제목으로 시작하지 않습니다."
    )

    assert len(result["key_points"]) >= 2, (
        "key_points가 2개 미만입니다."
    )

    print("PASS: model")
    print("PASS: markdown response format")
    print("PASS: markdown length")
    print("PASS: markdown heading")
    print("PASS: key points")
    print()
    print("PASS: STEP 2-25 Writer integration")


if __name__ == "__main__":
    asyncio.run(main())
