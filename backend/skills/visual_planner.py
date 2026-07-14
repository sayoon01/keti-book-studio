"""Visual Planner Agent.

역할: 챕터 내용과 사용 가능한 표 데이터(컬럼 목록)를 보고 어떤 시각자료가
필요한지 '명세'만 제안한다. 실제 실행(계산/그리기)은 하지 않는다.
"""

import json
import re
from typing import Callable, Optional

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 책의 시각자료를 기획하는 편집자입니다.
챕터 내용과 사용 가능한 표 데이터를 참고하여 필요한 시각자료를 제안하세요.

아래 JSON 형식으로만 응답하세요. 시각자료가 필요 없으면 visuals를 빈 배열로 응답해도 됩니다.
설명, 서두, 마크다운 코드블록 없이 순수 JSON만 출력합니다.

{
  "visuals": [
    {
      "visual_type": "table 또는 bar_chart 또는 line_chart 또는 scatter 또는 diagram 중 하나",
      "purpose": "이 시각자료가 왜 필요한지",
      "source_id": "사용할 자료의 source_id (표/차트인 경우 실제 컬럼이 있는 자료여야 함, 개념도는 null 가능)",
      "category_column": "표/차트인 경우 분류 기준 컬럼명 (모르면 null)",
      "value_column": "표/차트인 경우 수치 컬럼명 (모르면 null)",
      "caption": "시각자료 설명 캡션",
      "required": true 또는 false
    }
  ]
}

규칙:
- table/bar_chart/line_chart/scatter는 반드시 아래 제공된 '사용 가능한 표 데이터' 목록에
  있는 source_id와 실제 존재하는 컬럼명만 사용하세요. 컬럼명을 지어내지 마세요.
- diagram(개념도)은 데이터 없이 개념/구조 설명용으로 제안할 수 있습니다 (source_id는 null).
- 꼭 필요한 시각자료만 제안하세요. 억지로 채우지 마세요."""


def build_user_prompt(unit: dict, tabular_sources: list[dict], persona_visual_policy_md: str) -> str:
    tabular_text = (
        "\n".join(f"- source_id: {s['source_id']} / 컬럼: {s['columns']}" for s in tabular_sources)
        or "(표 형태 자료 없음)"
    )
    persona_part = f"\n\nPersona 시각화 지침:\n{persona_visual_policy_md}" if persona_visual_policy_md else ""
    must_cover = ", ".join(unit.get("must_cover", []) or [])
    return (
        f"챕터 제목: {unit.get('title', '')}\n"
        f"챕터 설명: {unit.get('description', '')}\n"
        f"반드시 다뤄야 할 내용: {must_cover}"
        f"{persona_part}\n\n"
        f"사용 가능한 표 데이터:\n{tabular_text}"
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


def plan_visuals(
    *,
    unit: dict,
    tabular_sources: list[dict],
    persona_visual_policy_md: str = "",
    llm_call: LlmCall,
) -> list[dict]:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(unit, tabular_sources, persona_visual_policy_md))
    data = _parse_json_response(raw)
    visuals = data.get("visuals") or []

    result = []
    for v in visuals:
        result.append(
            {
                "visual_type": v.get("visual_type", "table"),
                "purpose": v.get("purpose", ""),
                "source_id": v.get("source_id"),
                "category_column": v.get("category_column"),
                "value_column": v.get("value_column"),
                "caption": v.get("caption", ""),
                "required": bool(v.get("required", False)),
            }
        )
    return result
