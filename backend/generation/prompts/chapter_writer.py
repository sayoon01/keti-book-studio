from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WriterPrompts:
    system_prompt: str
    user_prompt: str


def build_chapter_writer_prompts(
    *,
    chapter_plan: dict[str, Any],
    research: dict[str, Any],
    book_context: dict[str, Any] | None = None,
    retry_reason: str | None = None,
) -> WriterPrompts:
    """
    Writer 전용 Markdown 생성 프롬프트를 구성한다.

    중요:
    Writer는 JSON을 반환하지 않는다.
    완성된 Markdown 본문만 반환한다.
    """

    book_payload = _compact_book_context(
        book_context or {}
    )

    plan_payload = _compact_chapter_plan(
        chapter_plan
    )

    research_payload = _compact_research(
        research
    )

    retry_instruction = _build_retry_instruction(
        retry_reason
    )

    system_prompt = """
당신은 전문 기술서와 교육용 교재를 작성하는 시니어 작가입니다.

사용자가 제공한 책 설정, 챕터 계획, 조사 자료를 바탕으로
하나의 완성된 챕터 본문을 작성하세요.

반드시 지켜야 할 출력 규칙:

1. 최종 출력은 Markdown 본문만 반환합니다.
2. JSON 객체를 반환하지 않습니다.
3. 응답 앞뒤에 설명이나 인사말을 추가하지 않습니다.
4. 전체 응답을 코드펜스로 감싸지 않습니다.
5. 첫 줄은 반드시 '# 챕터 제목' 형식으로 시작합니다.
6. 최소 1,500자 이상의 완성된 본문을 작성합니다.
7. 설명형 문단과 필요한 목록을 적절히 조합합니다.
8. 조사 자료에 없는 구체적인 수치나 사실을 만들어내지 않습니다.
9. 같은 문장이나 표현을 비정상적으로 반복하지 않습니다.
10. 문장을 중간에 끊지 않습니다.
11. 마지막에는 반드시 '## 핵심 정리' 섹션을 작성합니다.
12. 핵심 정리에는 3개 이상의 핵심 항목을 포함합니다.

권장 구조:

# 챕터 제목

도입 설명

## 첫 번째 주요 주제

개념 설명과 예시

## 두 번째 주요 주제

개념 설명과 예시

## 실제 적용 또는 주의사항

적용 방법과 주의사항

## 핵심 정리

- 핵심 내용 1
- 핵심 내용 2
- 핵심 내용 3
""".strip()

    user_prompt = f"""
다음 자료를 바탕으로 하나의 완성된 챕터를 작성하세요.

[책 설정]
{json.dumps(
    book_payload,
    ensure_ascii=False,
    indent=2,
)}

[챕터 계획]
{json.dumps(
    plan_payload,
    ensure_ascii=False,
    indent=2,
)}

[조사 자료]
{json.dumps(
    research_payload,
    ensure_ascii=False,
    indent=2,
)}

작성 요구사항:

- 챕터 계획의 제목과 목표를 중심으로 작성합니다.
- 단순한 목록 나열보다 연결된 설명형 문단을 우선합니다.
- 초급 독자도 이해할 수 있게 개념을 단계적으로 설명합니다.
- 필요한 경우 짧은 예시를 포함합니다.
- 조사 자료의 한계가 있다면 확정적으로 단정하지 않습니다.
- 최종 출력에는 Markdown 본문 외의 내용을 넣지 않습니다.
{retry_instruction}
""".strip()

    return WriterPrompts(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def _build_retry_instruction(
    retry_reason: str | None,
) -> str:
    if not retry_reason:
        return ""

    return f"""

[이전 결과 재시도 안내]

이전 생성 결과는 다음 이유로 사용할 수 없었습니다.

{retry_reason}

이번 응답에서는 다음을 반드시 보완하세요.

- Markdown 본문을 최소 1,500자 이상 작성합니다.
- 첫 줄을 '# 챕터 제목'으로 시작합니다.
- 문장을 중간에 끊지 않습니다.
- 같은 표현을 반복하지 않습니다.
- 마지막에 '## 핵심 정리'를 포함합니다.
""".rstrip()


def _compact_book_context(
    context: dict[str, Any],
) -> dict[str, Any]:
    allowed_keys = (
        "title",
        "description",
        "target_reader",
        "book_style",
        "goal",
        "language",
        "writing_guidelines",
    )

    return {
        key: context[key]
        for key in allowed_keys
        if key in context
        and context[key] not in (
            None,
            "",
            [],
            {},
        )
    }


def _compact_chapter_plan(
    plan: dict[str, Any],
) -> dict[str, Any]:
    allowed_keys = (
        "chapter_id",
        "unit_id",
        "title",
        "description",
        "objectives",
        "sections",
        "required_points",
        "target_length",
        "source_ids",
    )

    return {
        key: plan[key]
        for key in allowed_keys
        if key in plan
        and plan[key] not in (
            None,
            "",
            [],
            {},
        )
    }


def _compact_research(
    research: dict[str, Any],
) -> dict[str, Any]:
    allowed_keys = (
        "summary",
        "research_summary",
        "key_points",
        "findings",
        "facts",
        "evidence",
        "writing_guidance",
        "required_sections",
        "gaps",
        "source_ids",
        "limitations",
    )

    return {
        key: research[key]
        for key in allowed_keys
        if key in research
        and research[key] not in (
            None,
            "",
            [],
            {},
        )
    }
