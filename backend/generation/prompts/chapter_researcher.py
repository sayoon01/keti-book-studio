from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResearcherPromptBundle:
    """
    Researcher 모델 호출에 사용할 프롬프트 묶음.
    """

    system_prompt: str
    user_prompt: str


def build_chapter_researcher_prompts(
    *,
    book_config: dict[str, Any],
    chapter_plan: dict[str, Any],
    sources: list[dict[str, Any]] | None = None,
    previous_chapters: list[dict[str, Any]] | None = None,
) -> ResearcherPromptBundle:
    """
    챕터 집필 전에 필요한 조사 결과를 생성하는 프롬프트를 만든다.

    Researcher는 책 본문을 직접 작성하지 않는다.

    주요 역할:
    - 제공 자료에서 사실과 근거 추출
    - 챕터 목표에 맞는 핵심 정보 선별
    - Writer가 참고할 집필 방향 제안
    - 자료가 부족한 부분 표시
    """

    normalized_sources = _normalize_sources(sources or [])
    normalized_previous = _normalize_previous_chapters(
        previous_chapters or []
    )

    system_prompt = """
당신은 전문 서적 제작팀의 Researcher입니다.

당신의 역할은 책 본문을 작성하는 것이 아니라,
제공된 책 설정, 챕터 계획, 참고자료를 분석하여
Writer가 사용할 수 있는 조사 결과를 만드는 것입니다.

반드시 다음 원칙을 지키십시오.

1. 제공된 자료에서 확인할 수 있는 사실만 근거로 사용합니다.
2. 자료에 없는 내용을 사실처럼 만들어내지 않습니다.
3. 직접 확인할 수 없는 내용은 gaps에 명시합니다.
4. Writer가 바로 활용할 수 있도록 핵심 내용을 구조화합니다.
5. 결과는 반드시 유효한 JSON 객체 하나로만 출력합니다.
6. JSON 앞뒤에 설명, 인사말, Markdown 코드 블록을 붙이지 않습니다.
7. source_id가 있는 근거는 반드시 해당 source_id를 기록합니다.
8. findings와 evidence의 내용을 중복해서 길게 반복하지 않습니다.
9. 챕터 본문 전체를 대신 작성하지 않습니다.
10. 추론한 내용은 사실과 구분하여 표시합니다.

반드시 다음 JSON 구조를 사용하십시오.

{
  "chapter_id": "챕터 식별자",
  "title": "챕터 제목",
  "research_summary": "조사 결과 전체 요약",
  "findings": [
    {
      "topic": "핵심 주제",
      "content": "조사된 내용",
      "importance": "high | medium | low",
      "source_ids": ["source-001"],
      "is_inference": false
    }
  ],
  "evidence": [
    {
      "claim": "Writer가 본문에서 사용할 수 있는 주장",
      "support": "주장을 뒷받침하는 근거",
      "source_id": "source-001",
      "confidence": "high | medium | low"
    }
  ],
  "writing_guidance": [
    "Writer가 챕터를 구성할 때 참고할 지침"
  ],
  "required_sections": [
    "본문에 포함해야 할 섹션 또는 논점"
  ],
  "gaps": [
    "자료에서 확인할 수 없거나 추가 조사가 필요한 내용"
  ],
  "source_ids": [
    "실제로 사용한 source_id"
  ]
}
""".strip()

    user_payload = {
        "task": (
            "다음 책 설정과 챕터 계획을 분석하여 "
            "Writer가 사용할 Research Artifact를 생성하세요."
        ),
        "book_config": {
            "title": book_config.get("title", ""),
            "description": book_config.get("description", ""),
            "target_reader": book_config.get(
                "target_reader",
                "",
            ),
            "book_style": book_config.get("book_style", ""),
            "goal": book_config.get("goal", ""),
            "language": book_config.get("language", "ko"),
            "book_type": book_config.get("book_type", ""),
            "writing_guidelines": book_config.get(
                "writing_guidelines",
                [],
            ),
        },
        "chapter_plan": {
            "chapter_id": _get_chapter_id(chapter_plan),
            "title": chapter_plan.get("title", ""),
            "description": chapter_plan.get("description", ""),
            "goal": chapter_plan.get("goal", ""),
            "key_points": chapter_plan.get("key_points", []),
            "required_sections": chapter_plan.get(
                "required_sections",
                [],
            ),
            "source_ids": chapter_plan.get("source_ids", []),
            "target_length": chapter_plan.get(
                "target_length",
                chapter_plan.get("target_chars", 0),
            ),
        },
        "sources": normalized_sources,
        "previous_chapters": normalized_previous,
        "output_requirements": {
            "format": "json",
            "minimum_findings": 2,
            "minimum_writing_guidance": 2,
            "do_not_write_full_chapter": True,
            "use_only_provided_sources": True,
        },
    }

    user_prompt = json.dumps(
        user_payload,
        ensure_ascii=False,
        indent=2,
    )

    return ResearcherPromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def _normalize_sources(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    모델에 전달할 source 필드만 추린다.

    원본 파일 전체 메타데이터나 내부 저장소 정보가
    프롬프트에 무분별하게 들어가는 것을 방지한다.
    """

    normalized: list[dict[str, Any]] = []

    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue

        source_id = (
            source.get("source_id")
            or source.get("id")
            or f"source-{index:03d}"
        )

        content = (
            source.get("content")
            or source.get("text")
            or source.get("excerpt")
            or source.get("summary")
            or ""
        )

        normalized.append(
            {
                "source_id": str(source_id),
                "title": str(source.get("title", "")),
                "type": str(
                    source.get(
                        "type",
                        source.get("source_type", ""),
                    )
                ),
                "content": str(content),
                "metadata": source.get("metadata", {}),
            }
        )

    return normalized


def _normalize_previous_chapters(
    previous_chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    이전 챕터는 연속성 확인에 필요한 요약만 전달한다.
    """

    normalized: list[dict[str, Any]] = []

    for chapter in previous_chapters:
        if not isinstance(chapter, dict):
            continue

        normalized.append(
            {
                "chapter_id": _get_chapter_id(chapter),
                "title": str(chapter.get("title", "")),
                "summary": str(
                    chapter.get(
                        "summary",
                        chapter.get("research_summary", ""),
                    )
                ),
                "key_points": chapter.get("key_points", []),
            }
        )

    return normalized


def _get_chapter_id(
    chapter: dict[str, Any],
) -> str:
    """
    여러 구 버전의 식별자 필드명을 임시로 지원한다.
    """

    value = (
        chapter.get("chapter_id")
        or chapter.get("unit_id")
        or chapter.get("id")
        or ""
    )

    return str(value)
