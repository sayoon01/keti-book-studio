"""Research Agent.

역할: SourceDocument에서 추출된 텍스트를 받아 SourceProfile(요약/핵심주제/
강점/부족한 근거/추천 활용처)을 만든다.

LLM 호출부는 인자로 주입받는다(llm_call: Callable[[system, user], str]).
-> 실제로는 backend.services.llm_client.call_ollama가 주입되지만,
   테스트에서는 고정 응답을 돌려주는 가짜 함수로 교체해서 로직만 검증한다.
"""

import json
import re
from typing import Callable, Optional

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 문서/데이터 분석 전문가입니다.
주어진 자료를 분석하여 반드시 아래 JSON 스키마 형태로만 응답하세요.
설명, 서두, 마크다운 코드블록 없이 순수 JSON만 출력합니다.

{
  "summary": "자료 전체를 2~3문장으로 요약",
  "main_topics": ["핵심 주제1", "핵심 주제2"],
  "key_findings": ["핵심 발견/주장 1", "핵심 발견/주장 2"],
  "tables": [{"description": "표에 대한 설명", "usable_for_chart": true}],
  "limitations": ["이 자료만으로는 부족한 부분"],
  "recommended_uses": ["이 자료로 만들 수 있는 결과물 유형"]
}

목적(purpose)이 주어지면 그 목적에 맞는 관점으로 중요도를 판단하세요.
자료에 없는 내용을 지어내지 마세요."""


def build_user_prompt(text: str, purpose: Optional[str]) -> str:
    purpose_line = f"\n분석 목적: {purpose}\n" if purpose else "\n분석 목적: 일반 분석 (아직 특정 목적 없음)\n"
    return f"{purpose_line}\n자료 내용:\n{text}"


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw[:200]!r}")


def analyze_source(text: str, *, purpose: Optional[str], llm_call: LlmCall) -> dict:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(text, purpose))
    data = _parse_json_response(raw)

    return {
        "summary": data.get("summary", ""),
        "main_topics": data.get("main_topics", []) or [],
        "key_findings": data.get("key_findings", []) or [],
        "tables": data.get("tables", []) or [],
        "limitations": data.get("limitations", []) or [],
        "recommended_uses": data.get("recommended_uses", []) or [],
        "analysis_purpose": purpose,
    }
