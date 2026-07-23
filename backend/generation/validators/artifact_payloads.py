from __future__ import annotations

import re
from typing import Any


class ArtifactPayloadValidationError(ValueError):
    """LLM이 생성한 Artifact payload 형식이 잘못된 경우."""


def require_dict(
    payload: Any,
    *,
    artifact_type: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ArtifactPayloadValidationError(
            f"{artifact_type} payload는 dict여야 합니다."
        )

    return payload


def require_non_empty_string(
    payload: dict[str, Any],
    key: str,
    *,
    artifact_type: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ArtifactPayloadValidationError(
            f"{artifact_type}.{key}는 "
            "비어 있지 않은 문자열이어야 합니다."
        )

    return value.strip()


def require_list(
    payload: dict[str, Any],
    key: str,
    *,
    artifact_type: str,
) -> list[Any]:
    value = payload.get(key)

    if not isinstance(value, list):
        raise ArtifactPayloadValidationError(
            f"{artifact_type}.{key}는 list여야 합니다."
        )

    return value


def coerce_list(
    payload: dict[str, Any],
    key: str,
    *,
    artifact_type: str,
) -> list[Any]:
    """LLM이 문자열/누락으로 보낸 list 필드를 정규화한다."""
    value = payload.get(key)

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, dict):
        return [value]

    raise ArtifactPayloadValidationError(
        f"{artifact_type}.{key}는 list여야 합니다. "
        f"실제 타입={type(value).__name__}"
    )


def normalize_score(
    value: Any,
    *,
    default: float,
) -> float:
    if isinstance(value, bool):
        return default

    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))

    return default


def normalize_markdown_title(
    markdown: str,
    *,
    title: str,
) -> str:
    normalized = markdown.strip()

    heading_pattern = re.compile(
        rf"^\s*#\s+{re.escape(title)}\s*$",
        flags=re.MULTILINE,
    )

    matches = list(
        heading_pattern.finditer(normalized)
    )

    if not matches:
        return f"# {title}\n\n{normalized}"

    if len(matches) == 1:
        return normalized

    first_match = matches[0]

    before = normalized[:first_match.end()]
    after = normalized[first_match.end():]

    after = heading_pattern.sub(
        "",
        after,
    )

    after = re.sub(
        r"\n{3,}",
        "\n\n",
        after,
    ).strip()

    return f"{before}\n\n{after}".strip()


def validate_chapter_draft(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "CHAPTER_DRAFT"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    markdown = require_non_empty_string(
        result,
        "markdown",
        artifact_type=artifact_type,
    )

    if len(markdown) < 300:
        raise ArtifactPayloadValidationError(
            "CHAPTER_DRAFT.markdown이 너무 짧습니다. "
            f"현재 길이={len(markdown)}"
        )

    markdown = normalize_markdown_title(
        markdown,
        title=result["title"].strip(),
    )

    result["markdown"] = markdown

    return result


def validate_review_report(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "AGGREGATED_REVIEW_REPORT"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    issues = coerce_list(
        result,
        "issues",
        artifact_type=artifact_type,
    )

    suggestions = coerce_list(
        result,
        "suggestions",
        artifact_type=artifact_type,
    )

    result["quality_score"] = normalize_score(
        result.get("quality_score"),
        default=0.5,
    )

    result["passed"] = bool(
        result.get("passed", False)
    )

    result["issues"] = issues
    result["suggestions"] = suggestions

    return result


def validate_editorial_decision(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "EDITORIAL_DECISION"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "editorial_brief",
        artifact_type=artifact_type,
    )

    for key in (
        "structure_changes",
        "style_changes",
        "fact_check_items",
    ):
        result[key] = coerce_list(
            result,
            key,
            artifact_type=artifact_type,
        )

    return result


def validate_revised_chapter(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "REVISED_CHAPTER"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    markdown = require_non_empty_string(
        result,
        "markdown",
        artifact_type=artifact_type,
    )

    if len(markdown) < 300:
        raise ArtifactPayloadValidationError(
            "REVISED_CHAPTER.markdown이 너무 짧습니다. "
            f"현재 길이={len(markdown)}"
        )

    markdown = normalize_markdown_title(
        markdown,
        title=result["title"].strip(),
    )

    result["markdown"] = markdown

    result["applied_changes"] = coerce_list(
        result,
        "applied_changes",
        artifact_type=artifact_type,
    )

    result["unapplied_changes"] = coerce_list(
        result,
        "unapplied_changes",
        artifact_type=artifact_type,
    )

    return result


def validate_reader_report(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "READER_REPORT"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "reader_perspective",
        artifact_type=artifact_type,
    )

    result["hard_to_understand"] = coerce_list(
        result,
        "hard_to_understand",
        artifact_type=artifact_type,
    )

    result["improvements"] = coerce_list(
        result,
        "improvements",
        artifact_type=artifact_type,
    )

    result["satisfaction"] = normalize_score(
        result.get("satisfaction"),
        default=0.5,
    )

    return result


def validate_final_chapter(
    payload: Any,
) -> dict[str, Any]:
    artifact_type = "FINAL_CHAPTER"
    result = require_dict(
        payload,
        artifact_type=artifact_type,
    )

    require_non_empty_string(
        result,
        "title",
        artifact_type=artifact_type,
    )

    markdown = require_non_empty_string(
        result,
        "markdown",
        artifact_type=artifact_type,
    )

    if len(markdown) < 300:
        raise ArtifactPayloadValidationError(
            "FINAL_CHAPTER.markdown이 너무 짧습니다. "
            f"현재 길이={len(markdown)}"
        )

    markdown = normalize_markdown_title(
        markdown,
        title=result["title"].strip(),
    )

    result["markdown"] = markdown

    final_quality = result.get("final_quality")

    if not isinstance(final_quality, dict):
        final_quality = {}

    final_quality["score"] = normalize_score(
        final_quality.get("score"),
        default=0.5,
    )

    final_quality["reader_satisfaction"] = normalize_score(
        final_quality.get("reader_satisfaction"),
        default=0.5,
    )

    final_quality["publishable"] = bool(
        final_quality.get("publishable", False)
    )

    result["final_quality"] = final_quality
    result["publishable"] = bool(
        result.get(
            "publishable",
            final_quality["publishable"],
        )
    )

    return result
