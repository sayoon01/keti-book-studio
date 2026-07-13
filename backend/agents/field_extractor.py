"""Field Extractor.

역할: '3장 글자수 7천자로 바꿔줘' 같은 자연어에서 실제로 바꿀 필드/값만 뽑아낸다.
여기서 만든 dict는 그대로 BookConfigUpdate/BookUnitUpdate 생성자에 넘어간다 —
즉 폼이 보내는 것과 완전히 같은 모양이어야 한다.
"""

import json
import re
from typing import Callable

LlmCall = Callable[[str, str], str]

CONFIG_FIELDS_PROMPT = """당신은 사용자 메시지에서 책 설정 변경 사항만 뽑아내는 추출기입니다.

아래 필드 중 사용자가 실제로 언급한 것만 포함해서 JSON으로 응답하세요.
언급하지 않은 필드는 아예 넣지 마세요(빈 문자열이나 null로 채우지 마세요).

{
  "document_type": "...",
  "target_reader": "...",
  "purpose": "...",
  "tone": "...",
  "expertise_level": "beginner 또는 intermediate 또는 expert",
  "default_chars_per_chapter": 0,
  "citation_policy": "source_required 또는 optional 또는 none",
  "visual_density": "low 또는 medium 또는 high",
  "approval_mode": "safe 또는 balanced 또는 auto"
}

주의: chapter_count, total_target_characters는 이 방법으로 바꿀 수 없습니다
(목차 편집을 통해서만 자동으로 바뀝니다). 사용자가 이걸 요청해도 무시하세요."""

UNIT_FIELDS_PROMPT = """당신은 사용자 메시지에서 챕터(목차 항목) 변경 사항만 뽑아내는 추출기입니다.

아래 필드 중 사용자가 실제로 언급한 것만 포함해서 JSON으로 응답하세요.
언급하지 않은 필드는 아예 넣지 마세요.

{
  "title": "...",
  "description": "...",
  "target_characters": 0,
  "must_cover": ["..."],
  "custom_instructions": "..."
}"""


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw[:200]!r}")


def extract_config_patch(*, message: str, llm_call: LlmCall) -> dict:
    raw = llm_call(CONFIG_FIELDS_PROMPT, f"사용자 메시지: {message}")
    return _parse_json_response(raw)


def extract_unit_patch(*, message: str, llm_call: LlmCall) -> dict:
    raw = llm_call(UNIT_FIELDS_PROMPT, f"사용자 메시지: {message}")
    return _parse_json_response(raw)
