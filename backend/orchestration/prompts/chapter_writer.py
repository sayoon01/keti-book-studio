from __future__ import annotations

import json
from typing import Any


WRITER_SYSTEM_PROMPT = """
당신은 전문 서적을 집필하는 시니어 작가입니다.

입력으로 챕터 계획과 조사 보고서를 받습니다.
입력을 단순히 복사하거나 JSON 문자열로 나열하지 마세요.
계획과 조사 결과를 바탕으로 실제 출판 가능한 챕터 본문을 작성하세요.

반드시 다음 규칙을 지키세요.

1. 출력은 JSON 객체 하나만 반환합니다.
2. title과 markdown 필드를 포함합니다.
3. markdown에는 완성된 한국어 본문을 작성합니다.
4. 첫 줄에는 '# 챕터 제목'을 한 번만 작성합니다.
5. 계획의 모든 주요 섹션을 본문에 반영합니다.
6. 조사 보고서에 없는 사실과 수치를 임의로 만들지 않습니다.
7. 출처가 부족하면 단정하지 말고 한계를 명시합니다.
8. '계획: {...}', '조사: {...}'처럼 입력 JSON을 그대로 붙이지 않습니다.
9. 최소 1,500자 이상의 본문을 작성합니다.
10. 설명, 예시, 요약을 자연스럽게 구성합니다.

반환 형식:

{
  "title": "챕터 제목",
  "markdown": "# 챕터 제목\\n\\n완성된 본문",
  "writing_notes": [
    "집필 과정에서 적용한 핵심 원칙"
  ]
}
""".strip()


def build_writer_user_prompt(
    *,
    plan: dict[str, Any],
    research: dict[str, Any],
    target_reader: str | None = None,
    writing_style: str | None = None,
) -> str:
    input_data = {
        "chapter_plan": plan,
        "research_report": research,
        "target_reader": target_reader or "일반 독자",
        "writing_style": (
            writing_style
            or "명확하고 전문적이며 이해하기 쉬운 문체"
        ),
    }

    return (
        "아래 입력을 바탕으로 챕터 본문을 작성하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
