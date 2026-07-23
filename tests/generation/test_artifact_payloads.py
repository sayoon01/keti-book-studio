from __future__ import annotations

import pytest

from backend.generation.validators.artifact_payloads import (
    ArtifactPayloadValidationError,
    coerce_list,
    normalize_markdown_title,
    validate_chapter_draft,
    validate_revised_chapter,
    validate_review_report,
)


def _long_markdown(title: str) -> str:
    body = "본문 내용입니다. " * 30
    return f"# {title}\n\n{body}"


def test_validate_chapter_draft_accepts_valid_payload():
    title = "1장 AI 에이전트"

    result = validate_chapter_draft(
        {
            "title": title,
            "markdown": _long_markdown(title),
        }
    )

    assert result["title"] == title
    assert result["markdown"].startswith(f"# {title}")


def test_validate_chapter_draft_rejects_short_markdown():
    with pytest.raises(
        ArtifactPayloadValidationError,
        match="너무 짧습니다",
    ):
        validate_chapter_draft(
            {
                "title": "짧은 초안",
                "markdown": "짧음",
            }
        )


def test_normalize_markdown_title_removes_duplicate_heading():
    title = "1장 AI 에이전트"
    markdown = (
        f"# {title}\n\n"
        f"# {title}\n\n"
        "본문"
    )

    normalized = normalize_markdown_title(
        markdown,
        title=title,
    )

    assert normalized.count(f"# {title}") == 1
    assert "본문" in normalized


def test_validate_review_report_coerces_string_lists():
    result = validate_review_report(
        {
            "title": "검토 보고서",
            "issues": "구조 보완 필요",
            "suggestions": "예시 추가",
            "quality_score": 0.82,
        }
    )

    assert result["issues"] == ["구조 보완 필요"]
    assert result["suggestions"] == ["예시 추가"]
    assert result["quality_score"] == 0.82


def test_validate_revised_chapter_coerces_applied_changes():
    title = "1장 AI 에이전트"
    markdown = _long_markdown(title)

    result = validate_revised_chapter(
        {
            "title": title,
            "markdown": markdown,
            "applied_changes": "문단 구조 개선",
        }
    )

    assert result["applied_changes"] == ["문단 구조 개선"]


def test_coerce_list_returns_empty_for_missing_key():
    assert coerce_list(
        {},
        "items",
        artifact_type="TEST",
    ) == []


def test_old_orchestration_import_path_still_works():
    from backend.orchestration.artifact_payloads import (
        validate_chapter_draft as legacy_validate,
    )

    title = "호환 import"
    result = legacy_validate(
        {
            "title": title,
            "markdown": _long_markdown(title),
        }
    )

    assert result["title"] == title
