"""Intent Classifier.

역할: 사용자의 자연어 채팅 메시지를 구조화된 action으로 분류한다.
실제 실행(패치 값 추출, API 호출)은 Action Planner + Chat Controller가 담당한다.
"""

import json
import re
from typing import Callable, Optional

LlmCall = Callable[[str, str], str]

SUPPORTED_ACTIONS = {
    "ask",
    "edit_config",
    "edit_unit",
    "generate_outline",
    "approve_outline",
    "generate_chapter",
}

SYSTEM_PROMPT = """당신은 사용자의 채팅 메시지를 분석해 어떤 작업을 원하는지 분류하는 라우터입니다.

아래 JSON 형식으로만 응답하세요. 설명, 서두 없이 순수 JSON만 출력합니다.

{
  "action": "ask 또는 edit_config 또는 edit_unit 또는 generate_outline 또는 approve_outline 또는 generate_chapter 중 하나",
  "reasoning": "왜 이렇게 분류했는지 한 문장"
}

각 action의 의미:
- ask: 자료나 책 내용에 대해 질문하고 답변만 원함 (아무것도 바꾸지 않음)
- edit_config: 책 설정(제목, 대상 독자, 문체, 전문성 수준, 인용 정책 등)을 변경하고 싶어함
- edit_unit: 특정 챕터의 제목/설명/목표 글자수/필수 내용을 변경하고 싶어함
- generate_outline: 목차를 새로 생성하거나 완전히 다시 만들고 싶어함
- approve_outline: 목차를 승인하고 싶어함
- generate_chapter: 특정 챕터의 본문을 새로 쓰거나 다시 쓰고 싶어함"""


def build_user_prompt(message: str, scope_type: str, scope_id: Optional[str]) -> str:
    scope_line = f"현재 화면 범위: {scope_type}" + (f" ({scope_id})" if scope_id else "")
    return f"{scope_line}\n\n사용자 메시지: {message}"


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw[:200]!r}")


def classify_intent(
    *, message: str, scope_type: str = "general", scope_id: Optional[str] = None, llm_call: LlmCall
) -> dict:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(message, scope_type, scope_id))
    data = _parse_json_response(raw)
    action = data.get("action", "ask")
    if action not in SUPPORTED_ACTIONS:
        action = "ask"
    return {"action": action, "reasoning": data.get("reasoning", "")}
