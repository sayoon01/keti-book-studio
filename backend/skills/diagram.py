"""Diagram Agent (Visual Agent의 하위 역할).

역할: 데이터 기반이 아닌 개념도/구조도를 Mermaid 텍스트로 생성한다.
"""

from typing import Callable

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 개념도/구조도를 그리는 다이어그램 작가입니다.
Mermaid 문법으로 다이어그램 코드만 출력하세요. 설명, 서두, 코드블록 표시(```) 없이
graph TD 또는 flowchart TD 등으로 시작하는 Mermaid 코드 자체만 출력합니다."""


def build_user_prompt(purpose: str, unit: dict) -> str:
    return f"챕터 제목: {unit.get('title', '')}\n다이어그램 목적: {purpose}"


def generate_diagram(*, purpose: str, unit: dict, llm_call: LlmCall) -> str:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(purpose, unit))
    return raw.strip().strip("`").strip()
