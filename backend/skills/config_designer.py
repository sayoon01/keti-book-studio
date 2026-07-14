"""Config Designer Agent.

역할: 여러 SourceProfile(자료 분석 결과)과 사용자 목적을 받아
BookConfig 초안 + 추천 Persona를 만든다.

주의: chapter_count/total_target_characters 는 Phase 1 설계상 outline의
unit 합계로만 정해지므로, 여기서는 '추천 챕터 수(suggested_chapter_count)'를
참고용 힌트로만 반환하고 config에 직접 쓰지 않는다.
"""

import json
import re
from typing import Callable, Optional

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 책/문서 기획 전문가입니다.
분석된 자료와 사용자 목적을 참고하여 책 설정을 제안하세요.

아래 JSON 형식으로만, 모든 필드를 반드시 채워서 응답하세요.
빈 객체({})나 일부 필드 생략은 허용되지 않습니다.
설명, 서두, 마크다운 코드블록 없이 순수 JSON 객체 하나만 출력하세요.

각 필드의 허용 값:
- document_type: technical_guide, report, textbook, novel, guide, business_report, general 중 하나
- expertise_level: beginner, intermediate, expert 중 하나
- citation_policy: source_required, optional, none 중 하나
- visual_density: low, medium, high 중 하나
- recommended_persona_name: 아래 제공되는 Persona 후보 목록의 이름 중 정확히 하나를 그대로 사용

예시 응답 형식(아래 값은 예시일 뿐이며, 실제로는 주어진 자료 내용에 맞게 채우세요):
{
  "document_type": "technical_guide",
  "target_reader": "반도체 공정 엔지니어",
  "purpose": "ALD 공정 파라미터 이해를 돕는 기술서 작성",
  "tone": "전문적이고 근거 중심",
  "expertise_level": "expert",
  "suggested_chapter_count": 8,
  "default_chars_per_chapter": 5000,
  "citation_policy": "source_required",
  "visual_density": "high",
  "recommended_persona_name": "기술 전문가",
  "recommendation_reason": "공정 변수와 수치 근거를 다루는 자료이기 때문",
  "alternative_persona_names": ["데이터 분석가"]
}

자료에 없는 내용을 지어내지 말고, 실제 자료 성격에 맞게 판단하세요."""


def build_user_prompt(profiles: list[dict], purpose: Optional[str], persona_options: list[dict]) -> str:
    profiles_text = "\n\n".join(
        f"[자료 {i + 1}]\n"
        f"요약: {p.get('summary', '')}\n"
        f"주제: {', '.join(p.get('main_topics', []) or [])}\n"
        f"핵심 발견: {', '.join(p.get('key_findings', []) or [])}\n"
        f"부족한 근거: {', '.join(p.get('limitations', []) or [])}\n"
        f"추천 활용처: {', '.join(p.get('recommended_uses', []) or [])}"
        for i, p in enumerate(profiles)
    )
    personas_text = "\n".join(
        f"- {p['name']}: {p.get('description', '')}" for p in persona_options
    )
    purpose_line = (
        f"사용자가 밝힌 목적: {purpose}"
        if purpose
        else "사용자가 아직 목적을 밝히지 않았습니다 - 자료 성격으로 추론하세요."
    )
    return (
        f"{purpose_line}\n\n"
        f"분석된 자료들:\n{profiles_text}\n\n"
        f"선택 가능한 Persona 후보:\n{personas_text}"
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


def suggest_book_config(
    *,
    profiles: list[dict],
    purpose: Optional[str],
    persona_options: list[dict],
    llm_call: LlmCall,
) -> dict:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(profiles, purpose, persona_options))
    data = _parse_json_response(raw)

    name_to_id = {p["name"]: p["persona_id"] for p in persona_options}
    recommended_id = name_to_id.get(data.get("recommended_persona_name"))
    alt_ids = [
        name_to_id[n] for n in (data.get("alternative_persona_names") or []) if n in name_to_id
    ]

    return {
        "config_patch": {
            "document_type": data.get("document_type", "general"),
            "target_reader": data.get("target_reader", ""),
            "purpose": data.get("purpose", purpose or ""),
            "tone": data.get("tone", ""),
            "expertise_level": data.get("expertise_level", "intermediate"),
            "default_chars_per_chapter": int(data.get("default_chars_per_chapter", 5000)),
            "citation_policy": data.get("citation_policy", "source_required"),
            "visual_density": data.get("visual_density", "medium"),
        },
        "suggested_chapter_count": int(data.get("suggested_chapter_count", 8)),
        "recommended_persona_id": recommended_id,
        "recommendation_reason": data.get("recommendation_reason", ""),
        "alternative_persona_ids": alt_ids,
    }
