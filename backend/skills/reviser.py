"""Reviser Agent.

역할: Reviewer가 찾은 문제만 반영해서 본문을 고친다.
Writer와 같은 모델을 쓴다 — 검토는 다른 시각이 필요하지만,
수정은 원래 문체를 유지해야 하므로 같은 모델이 유리하다.
"""

from typing import Callable

LlmCall = Callable[[str, str], str]

BASE_RULES = """당신은 편집자의 검토 의견을 반영해 본문을 수정하는 작가입니다.

# 규칙
- 지적된 문제만 고치세요. 문제 없는 부분은 최대한 원문 그대로 유지하세요.
- 원문의 문체와 구조를 유지하세요.
- 근거 자료에 없는 내용을 새로 지어내지 마세요.
- 순수 수정된 본문 전체를 출력하세요. 어떤 부분을 고쳤는지 설명하지 마세요."""


def build_system_prompt(persona_writer_md: str) -> str:
    persona_part = f"\n\n# Persona 지침\n{persona_writer_md}" if persona_writer_md else ""
    return BASE_RULES + persona_part


def build_user_prompt(body_md: str, issues: list[dict], unit: dict) -> str:
    issues_text = "\n".join(
        f"- [{issue.get('type', '')}] {issue.get('description', '')} "
        f"(위치 힌트: {issue.get('location_hint', '')})"
        for issue in issues
    )
    return (
        f"챕터 제목: {unit.get('title', '')}\n\n"
        f"검토자가 지적한 문제:\n{issues_text}\n\n"
        f"원문:\n{body_md}"
    )


def revise_chapter(
    *,
    body_md: str,
    issues: list[dict],
    unit: dict,
    persona_writer_md: str = "",
    llm_call: LlmCall,
) -> str:
    system_prompt = build_system_prompt(persona_writer_md)
    user_prompt = build_user_prompt(body_md, issues, unit)
    revised = llm_call(system_prompt, user_prompt)
    return revised.strip()
