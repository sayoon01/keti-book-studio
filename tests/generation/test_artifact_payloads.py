from __future__ import annotations

import pytest

from backend.generation.validators.artifact_payloads import (
    ArtifactPayloadValidationError,
    ArtifactValidationError,
    validate_chapter_draft,
    validate_research_artifact,
    validate_review_artifact,
)


def _long_markdown(title: str) -> str:
    paragraphs = [
        "에이전트는 목표를 중심으로 판단하고 행동한다.",
        "모델은 추론을 담당하고 도구는 외부 작업을 수행한다.",
        "상태는 연속된 실행 맥락을 유지하는 데 사용된다.",
        "일반 LLM 호출과 달리 여러 단계의 실행 흐름을 가질 수 있다.",
        "실제 시스템에서는 오류 처리와 재시도 전략이 중요하다.",
        "독자가 개념을 이해할 수 있도록 예시와 설명을 함께 제공한다.",
    ]
    body = "\n\n".join(paragraphs * 3)
    return f"# {title}\n\n{body}"


def test_validate_chapter_draft_accepts_valid_payload():
    title = "1장 AI 에이전트"

    result = validate_chapter_draft(
        {
            "chapter_id": "chapter-01",
            "title": title,
            "summary": "AI 에이전트의 기본 개념을 설명합니다.",
            "markdown": _long_markdown(title),
            "key_points": [
                "에이전트는 목표 지향적으로 동작한다.",
                "도구와 상태를 활용할 수 있다.",
            ],
            "source_ids": ["src-1"],
        }
    )

    assert result["artifact_type"] == "CHAPTER_DRAFT"
    assert result["title"] == title
    assert result["summary"].startswith("AI 에이전트")
    assert len(result["key_points"]) == 2
    assert result["source_ids"] == ["src-1"]


def test_validate_chapter_draft_rejects_short_markdown():
    with pytest.raises(
        ArtifactValidationError,
        match="너무 짧습니다",
    ):
        validate_chapter_draft(
            {
                "chapter_id": "chapter-01",
                "title": "짧은 초안",
                "summary": "요약이 충분히 길어야 합니다.",
                "markdown": "짧음",
                "key_points": ["a", "b"],
            }
        )


def test_validate_research_artifact_accepts_valid_payload():
    result = validate_research_artifact(
        {
            "chapter_id": "chapter-01",
            "title": "ADK 기본 개념",
            "research_summary": (
                "ADK Agent와 Tool, Session의 "
                "역할을 정리한 조사 결과입니다."
            ),
            "findings": [
                {
                    "topic": "Agent",
                    "content": (
                        "Agent는 모델과 도구를 "
                        "조합해 요청을 처리한다."
                    ),
                    "importance": "high",
                    "source_ids": ["source-1"],
                    "is_inference": False,
                }
            ],
            "evidence": [
                {
                    "claim": "Agent는 도구를 사용할 수 있다.",
                    "support": "자료에서 Tool 실행을 설명함",
                    "source_id": "source-1",
                    "confidence": "high",
                }
            ],
            "writing_guidance": [
                "개념 설명 후 예시를 배치한다.",
            ],
            "required_sections": ["AI Agent란"],
            "gaps": ["Memory 세부 구현"],
            "source_ids": ["source-1"],
        }
    )

    assert result["artifact_type"] == "RESEARCH_ARTIFACT"
    assert result["chapter_id"] == "chapter-01"
    assert "summary" not in result
    assert "key_points" not in result
    assert len(result["findings"]) == 1
    assert result["source_ids"] == ["source-1"]


def test_validate_research_artifact_rejects_empty_findings():
    with pytest.raises(
        ArtifactPayloadValidationError,
        match="findings",
    ):
        validate_research_artifact(
            {
                "chapter_id": "chapter-01",
                "title": "제목",
                "research_summary": (
                    "조사 요약이 충분히 길어야 통과합니다."
                ),
                "findings": [],
                "writing_guidance": ["지침"],
            }
        )


def test_validate_review_artifact_accepts_valid_payload():
    result = validate_review_artifact(
        {
            "chapter_id": "chapter-01",
            "title": "검토 대상",
            "overall_score": 72,
            "verdict": "minor_revision",
            "review_summary": (
                "전체 구조는 적절하지만 일부 표현 보완이 "
                "필요합니다."
            ),
            "strengths": ["핵심 개념이 명확하다."],
            "issues": [
                {
                    "category": "clarity",
                    "severity": "minor",
                    "location": "도입부",
                    "description": "용어 설명이 부족하다.",
                    "recommendation": "용어를 먼저 정의한다.",
                    "source_ids": [],
                }
            ],
            "revision_instructions": [
                "도입부에서 Agent 용어를 정의한다.",
            ],
            "fact_check_items": [],
            "missing_sections": [],
            "source_ids": [],
        }
    )

    assert result["artifact_type"] == "REVIEW_ARTIFACT"
    assert result["verdict"] == "minor_revision"
    assert result["overall_score"] == 72


def test_old_orchestration_import_path_still_works():
    from backend.orchestration.artifact_payloads import (
        validate_chapter_draft as legacy_validate,
    )

    title = "호환 import"
    result = legacy_validate(
        {
            "chapter_id": "chapter-legacy",
            "title": title,
            "summary": "호환성 확인용 요약입니다.",
            "markdown": _long_markdown(title),
            "key_points": [
                "핵심 1",
                "핵심 2",
            ],
        }
    )

    assert result["title"] == title
