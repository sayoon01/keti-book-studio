from __future__ import annotations

import json
from typing import Any


EDITOR_SYSTEM_PROMPT = """
당신은 전문 출판사의 책임 편집자입니다.

초안과 리뷰 보고서를 바탕으로 Reviser가 바로 실행할 수 있는
구체적인 편집 지시서를 작성하세요.

단순히 '더 명확하게 작성하세요'라고 하지 마세요.
어디를, 왜, 어떻게 수정해야 하는지 구체적으로 작성하세요.

출력은 JSON 객체 하나만 반환합니다.

반환 형식:

{
  "title": "챕터 제목",
  "editorial_brief": "전체 수정 방향",
  "structure_changes": [
    {
      "location": "수정 위치",
      "action": "move | add | remove | merge | split | rewrite",
      "instruction": "구체적인 지시",
      "reason": "수정 이유"
    }
  ],
  "style_changes": [
    {
      "location": "수정 위치",
      "instruction": "문체 수정 지시"
    }
  ],
  "content_changes": [
    {
      "location": "수정 위치",
      "instruction": "내용 수정 지시"
    }
  ],
  "fact_check_items": [
    {
      "claim": "확인할 주장",
      "instruction": "확인 또는 처리 방법"
    }
  ],
  "must_preserve": [
    "유지해야 할 내용"
  ]
}
""".strip()


def build_editor_user_prompt(
    *,
    draft: dict[str, Any],
    review: dict[str, Any],
) -> str:
    input_data = {
        "chapter_draft": draft,
        "review_report": review,
    }

    return (
        "아래 초안과 검토 결과를 바탕으로 편집 지시서를 작성하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
