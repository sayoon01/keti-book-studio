"""Outline Planner Agent.

역할: SourceProfile들 + BookConfig + Persona(planner.md)를 참고해서
장 단위 목차 초안(제목/설명/목표 글자수/필수 포함 내용)을 만든다.

실제 DB 반영(BookUnit 생성)은 API 레이어(backend/api/outlines.py)가 담당하고,
이 모듈은 순수하게 '자료 -> 목차안' 변환만 책임진다 (테스트하기 쉽게 분리).
"""

import json
import re
from typing import Callable, Optional

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 책의 목차를 설계하는 전문 편집자입니다.
분석된 자료, 책 설정, Persona 지침을 참고하여 장(chapter) 단위 목차를 제안하세요.

아래 JSON 형식으로만, 모든 필드를 반드시 채워서 응답하세요.
빈 배열이나 필드 생략은 허용되지 않습니다.
설명, 서두, 마크다운 코드블록 없이 순수 JSON 객체 하나만 출력하세요.

예시 응답 형식(아래 값은 예시일 뿐이며, 실제로는 주어진 자료와 설정에 맞게 채우세요):
{
  "chapters": [
    {
      "title": "1장. ALD 공정의 기본 원리",
      "description": "ALD 공정의 정의와 반응 사이클을 설명한다.",
      "target_characters": 5000,
      "must_cover": ["ALD 정의", "반응 사이클", "CVD와의 차이"]
    },
    {
      "title": "2장. 주요 공정 파라미터",
      "description": "온도, 압력 등 핵심 변수를 설명한다.",
      "target_characters": 6000,
      "must_cover": ["온도", "압력", "전구체 공급 시간"]
    }
  ]
}

각 장의 target_characters 합이 전체 목표 분량에 가깝도록 배분하세요.
자료에 없는 내용을 지어내지 말고, must_cover는 실제 자료에 등장하는 주제로만 채우세요."""


def build_user_prompt(
    profiles: list[dict],
    config: dict,
    persona_planner_md: str,
    chapter_count_hint: int,
) -> str:
    profiles_text = "\n\n".join(
        f"[자료 {i + 1}]\n"
        f"요약: {p.get('summary', '')}\n"
        f"주제: {', '.join(p.get('main_topics', []) or [])}\n"
        f"핵심 발견: {', '.join(p.get('key_findings', []) or [])}"
        for i, p in enumerate(profiles)
    )
    total_chars = chapter_count_hint * config.get("default_chars_per_chapter", 5000)
    return (
        f"책 설정:\n"
        f"- 문서 유형: {config.get('document_type', '')}\n"
        f"- 대상 독자: {config.get('target_reader', '')}\n"
        f"- 작성 목적: {config.get('purpose', '')}\n"
        f"- 전문성 수준: {config.get('expertise_level', '')}\n"
        f"- 권장 장 수: {chapter_count_hint}\n"
        f"- 전체 목표 분량(대략): {total_chars}자\n\n"
        f"Persona 목차 설계 지침:\n{persona_planner_md or '(별도 지침 없음)'}\n\n"
        f"분석된 자료들:\n{profiles_text}"
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


def suggest_outline(
    *,
    profiles: list[dict],
    config: dict,
    persona_planner_md: str = "",
    chapter_count_hint: int = 8,
    llm_call: LlmCall,
) -> list[dict]:
    raw = llm_call(
        SYSTEM_PROMPT,
        build_user_prompt(profiles, config, persona_planner_md, chapter_count_hint),
    )
    data = _parse_json_response(raw)

    chapters = data.get("chapters") or []
    result = []
    for ch in chapters:
        result.append(
            {
                "title": ch.get("title", "제목 없음"),
                "description": ch.get("description", ""),
                "target_characters": int(ch.get("target_characters", 5000)),
                "must_cover": ch.get("must_cover", []) or [],
            }
        )
    return result
