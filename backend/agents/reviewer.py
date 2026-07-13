"""Reviewer Agent.

역할: Writer가 쓴 본문을 근거 자료와 대조해서 문제점을 찾는다.
Writer와 다른 모델을 쓰는 게 핵심 — 같은 모델이 쓰고 검토하면
그 모델의 맹점을 그대로 못 잡아내기 때문.

JSON 구조화 응답을 강제한다(json_mode=True 로 호출되는 llm_call 주입).
"""

import json
import re
from typing import Callable

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 문서 검토 전문가입니다. 다른 작가가 쓴 챕터 본문을
근거 자료와 대조하여 검토하세요. 당신이 직접 글을 쓰는 것이 아니라, 문제점만 찾습니다.

아래 JSON 형식으로만 응답하세요. 설명, 서두, 마크다운 코드블록 없이 순수 JSON만 출력합니다.

{
  "issues": [
    {
      "type": "근거 부족 또는 논리 비약 또는 과장 또는 일관성 오류 또는 필수내용 누락 중 하나",
      "description": "무엇이 문제인지 구체적으로 설명",
      "location_hint": "본문에서 문제가 있는 부분을 15단어 이내로 짧게 인용"
    }
  ],
  "needs_revision": true 또는 false,
  "overall_comment": "전반적인 평가 한두 문장"
}

특히 다음을 확인하세요:
- 근거 자료에 없는 수치, 통계, 인용을 지어낸 부분
- 원인과 결과를 근거 없이 단정한 부분
- '반드시 다뤄야 할 내용' 중 본문에 빠진 것
- 앞뒤 문장이 모순되는 부분

문제가 전혀 없으면 issues를 빈 배열로, needs_revision을 false로 응답하세요.
사소한 문체 취향 차이는 issue로 잡지 마세요 — 사실/근거/누락 문제만 잡으세요."""


def build_user_prompt(body_md: str, unit: dict, persona_reviewer_md: str, evidence_chunks: list[str]) -> str:
    persona_part = f"\n\nPersona 검토 기준:\n{persona_reviewer_md}" if persona_reviewer_md else ""
    must_cover = ", ".join(unit.get("must_cover", []) or [])
    evidence_text = "\n\n---\n\n".join(evidence_chunks)
    return (
        f"챕터 제목: {unit.get('title', '')}\n"
        f"반드시 다뤄야 할 내용: {must_cover}"
        f"{persona_part}\n\n"
        f"근거 자료:\n{evidence_text}\n\n"
        f"검토할 본문:\n{body_md}"
    )


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw[:200]!r}")


def review_chapter(
    *,
    body_md: str,
    unit: dict,
    persona_reviewer_md: str = "",
    evidence_chunks: list[str],
    llm_call: LlmCall,
) -> dict:
    raw = llm_call(
        SYSTEM_PROMPT,
        build_user_prompt(body_md, unit, persona_reviewer_md, evidence_chunks),
    )
    data = _parse_json_response(raw)
    return {
        "issues": data.get("issues", []) or [],
        "needs_revision": bool(data.get("needs_revision", False)),
        "overall_comment": data.get("overall_comment", ""),
    }
