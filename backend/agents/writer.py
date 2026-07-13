"""Writer Agent.

역할: 챕터 계획(BookUnit) + 근거 자료 + Persona writer.md 지침을 받아
실제 챕터 본문(마크다운)을 작성한다.

Research/Config/Outline Agent와 달리 JSON이 아니라 순수 텍스트를 반환한다
(json_mode=False 로 호출되는 llm_call을 주입받는다).
"""

from typing import Callable

LlmCall = Callable[[str, str], str]

BASE_RULES = """당신은 책의 한 챕터를 작성하는 작가입니다.

# 공통 규칙
- 마크다운 형식으로 작성하세요 (챕터 제목은 이미 있으니 본문은 ## 소제목부터 시작).
- 목표 분량에 최대한 맞추되, 근거 없는 내용으로 억지로 채우지 마세요.
- 주어진 근거 자료에 없는 사실, 수치, 통계, 인용을 지어내지 마세요.
- '반드시 다뤄야 할 내용'을 모두 포함하세요.
- 순수 본문만 출력하세요. 서두 인사, 메타 설명, "다음은 본문입니다" 같은 코멘트를 쓰지 마세요."""


def build_system_prompt(persona_writer_md: str) -> str:
    persona_part = f"\n\n# Persona 지침\n{persona_writer_md}" if persona_writer_md else ""
    return BASE_RULES + persona_part


def build_user_prompt(unit: dict, book_config: dict, evidence_chunks: list[str]) -> str:
    evidence_text = "\n\n---\n\n".join(evidence_chunks)
    must_cover = ", ".join(unit.get("must_cover", []) or [])
    return (
        f"책 설정:\n"
        f"- 대상 독자: {book_config.get('target_reader', '')}\n"
        f"- 문체: {book_config.get('tone', '')}\n"
        f"- 전문성 수준: {book_config.get('expertise_level', '')}\n\n"
        f"이번 챕터:\n"
        f"- 제목: {unit.get('title', '')}\n"
        f"- 설명: {unit.get('description', '')}\n"
        f"- 목표 분량: 약 {unit.get('target_characters', 5000)}자\n"
        f"- 반드시 다뤄야 할 내용: {must_cover}\n\n"
        f"근거 자료:\n{evidence_text}"
    )


def write_chapter(
    *,
    unit: dict,
    book_config: dict,
    persona_writer_md: str,
    evidence_chunks: list[str],
    llm_call: LlmCall,
) -> str:
    system_prompt = build_system_prompt(persona_writer_md)
    user_prompt = build_user_prompt(unit, book_config, evidence_chunks)
    body = llm_call(system_prompt, user_prompt)
    return body.strip()
