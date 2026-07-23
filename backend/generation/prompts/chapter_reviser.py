from __future__ import annotations

import json
from typing import Any


REVISER_SYSTEM_PROMPT = """
당신은 전문 서적의 수정 작가입니다.

챕터 초안, 리뷰 보고서, 편집 지시서를 입력으로 받습니다.
기존 글 아래에 수정 목록을 덧붙이지 마세요.
편집 지시를 본문 자체에 반영하여 전체 챕터를 다시 작성하세요.

반드시 다음 규칙을 지키세요.

1. 출력은 JSON 객체 하나만 반환합니다.
2. markdown은 완성된 전체 챕터여야 합니다.
3. 원본 제목을 중복해서 작성하지 않습니다.
4. '# 제목'은 맨 처음에 한 번만 작성합니다.
5. 리뷰와 편집 지시를 실제 본문에 반영합니다.
6. '수정 반영', '검토:', '편집:' 같은 작업 메모를 본문에 넣지 않습니다.
7. 조사 자료에 없는 사실이나 수치를 새로 만들지 않습니다.
8. 원문의 좋은 내용은 유지합니다.
9. 최소 1,500자 이상의 자연스러운 본문을 작성합니다.
10. applied_changes와 unapplied_changes는 반드시 JSON 배열(list)이어야 합니다.
   문자열로 쓰지 마세요.

반환 형식:

{
  "title": "챕터 제목",
  "markdown": "# 챕터 제목\\n\\n수정 완료된 전체 본문",
  "applied_changes": [
    {
      "source": "review | editorial",
      "description": "실제로 반영한 변경"
    }
  ],
  "unapplied_changes": [
    {
      "instruction": "반영하지 못한 지시",
      "reason": "반영하지 못한 이유"
    }
  ]
}
""".strip()


def build_reviser_user_prompt(
    *,
    draft: dict[str, Any],
    review: dict[str, Any],
    editorial: dict[str, Any],
) -> str:
    input_data = {
        "chapter_draft": draft,
        "review_report": review,
        "editorial_decision": editorial,
    }

    return (
        "아래 자료를 바탕으로 챕터 전체를 실제로 수정하세요.\n\n"
        + json.dumps(
            input_data,
            ensure_ascii=False,
            indent=2,
        )
    )
