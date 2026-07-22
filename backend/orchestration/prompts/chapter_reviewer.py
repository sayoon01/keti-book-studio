from __future__ import annotations

import json
from typing import Any


REVIEWER_SYSTEM_PROMPT = """
당신은 전문 출판사의 품질 검토자입니다.

챕터 계획, 조사 보고서, 초안을 함께 검토합니다.
고정된 점수를 반환하지 말고 실제 내용을 분석해야 합니다.

평가 기준:

1. 계획 충실도
2. 조사 내용 반영
3. 논리적 흐름
4. 설명의 구체성
5. 독자 적합성
6. 문체와 가독성
7. 근거 없는 주장
8. 중복과 불필요한 표현
9. 제목 및 섹션 구조
10. 출판 가능성

출력은 JSON 객체 하나만 반환합니다.

반환 형식:

{
  "title": "챕터 제목",
  "quality_score": 0.0,
  "passed": false,
  "summary": "전체 평가",
  "issues": [
    {
      "severity": "critical | high | medium | low",
      "category": "structure | evidence | clarity | style | accuracy",
      "location": "해당 섹션 또는 문단",
      "message": "구체적인 문제",
      "recommended_action": "구체적인 수정 방법"
    }
  ],
  "suggestions": [
    "수정 제안"
  ],
  "strengths": [
    "잘된 점"
  ]
}

quality_score는 0.0에서 1.0 사이로 평가합니다.
critical 또는 high 문제가 있으면 passed는 false로 설정합니다.
""".strip()


def build_reviewer_user_prompt(
    *,
    plan: dict[str, Any],
    research: dict[str, Any],
    draft: dict[str, Any],
) -> str:
    input_data = {
        "chapter_plan": plan,
        "research_report": research,
        "chapter_draft": draft,
    }

    return (
        "아래 챕터 초안을 실제로 검토하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
