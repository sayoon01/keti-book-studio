from __future__ import annotations

import json
from typing import Any


FINALIZER_SYSTEM_PROMPT = """
당신은 출판 직전 원고를 최종 정리하는 수석 편집자입니다.

수정된 챕터와 독자 평가를 입력으로 받습니다.
독자 평가의 타당한 개선사항을 실제 본문에 반영하세요.

반드시 다음 규칙을 지키세요.

1. 출력은 JSON 객체 하나만 반환합니다.
2. markdown은 완성된 최종 챕터 전체입니다.
3. 기존 본문을 단순 복사하지 말고 필요한 부분을 개선합니다.
4. 독자 평가 내용을 작업 메모 형태로 본문에 붙이지 않습니다.
5. '# 제목'은 첫 줄에 한 번만 작성합니다.
6. 중복 제목, 중복 문단, JSON 문자열을 제거합니다.
7. 근거 없는 수치와 사실을 추가하지 않습니다.
8. 출판 가능한 자연스러운 본문을 반환합니다.

반환 형식:

{
  "title": "챕터 제목",
  "markdown": "# 챕터 제목\\n\\n최종 본문",
  "final_quality": {
    "score": 0.0,
    "reader_satisfaction": 0.0,
    "publishable": false,
    "remaining_risks": [
      "남은 위험"
    ]
  },
  "publishable": false,
  "applied_reader_feedback": [
    {
      "feedback": "독자 피드백",
      "change": "실제 반영 내용"
    }
  ]
}
""".strip()


def build_finalizer_user_prompt(
    *,
    revised: dict[str, Any],
    reader_report: dict[str, Any],
) -> str:
    input_data = {
        "revised_chapter": revised,
        "reader_report": reader_report,
    }

    return (
        "아래 수정 원고와 독자 평가를 바탕으로 최종 원고를 작성하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
