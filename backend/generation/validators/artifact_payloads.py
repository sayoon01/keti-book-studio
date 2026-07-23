from __future__ import annotations

import re
from typing import Any


class ArtifactValidationError(ValueError):
    """
    Generation Artifact 구조나 품질이 올바르지 않을 때 발생한다.
    """


# 기존 테스트/서비스 호환 Alias
ArtifactPayloadValidationError = ArtifactValidationError


# =====================================================================
# Research Artifact
# =====================================================================


def validate_research_artifact(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Researcher 결과를 검증하고 정본 RESEARCH_ARTIFACT로 정규화한다.

    주의:
    - summary를 생성하지 않는다.
    - key_points를 생성하지 않는다.
    - 구 경로 호환은 adapters/legacy_artifact_adapter.py가 담당한다.
    """

    if not isinstance(payload, dict):
        raise ArtifactValidationError(
            "Research Artifact는 dictionary여야 합니다."
        )

    chapter_id = _require_string(
        payload,
        "chapter_id",
        minimum_length=1,
    )

    title = _require_string(
        payload,
        "title",
        minimum_length=1,
    )

    research_summary = _require_string(
        payload,
        "research_summary",
        minimum_length=20,
    )

    findings = _validate_findings(
        payload.get("findings")
    )

    evidence = _validate_evidence(
        payload.get("evidence", [])
    )

    writing_guidance = _normalize_string_list(
        payload.get("writing_guidance", []),
        field_name="writing_guidance",
    )

    required_sections = _normalize_string_list(
        payload.get("required_sections", []),
        field_name="required_sections",
    )

    gaps = _normalize_string_list(
        payload.get("gaps", []),
        field_name="gaps",
    )

    explicit_source_ids = _normalize_string_list(
        payload.get("source_ids", []),
        field_name="source_ids",
    )

    if not findings:
        raise ArtifactValidationError(
            "Research Artifact에는 findings가 "
            "최소 1개 이상 필요합니다."
        )

    if not writing_guidance:
        raise ArtifactValidationError(
            "Research Artifact에는 writing_guidance가 "
            "최소 1개 이상 필요합니다."
        )

    collected_source_ids = set(explicit_source_ids)

    for finding in findings:
        collected_source_ids.update(
            finding.get("source_ids", [])
        )

    for evidence_item in evidence:
        source_id = str(
            evidence_item.get("source_id", "")
        ).strip()

        if source_id:
            collected_source_ids.add(source_id)

    return {
        "artifact_type": "RESEARCH_ARTIFACT",
        "chapter_id": chapter_id,
        "title": title,
        "research_summary": research_summary,
        "findings": findings,
        "evidence": evidence,
        "writing_guidance": writing_guidance,
        "required_sections": required_sections,
        "gaps": gaps,
        "source_ids": sorted(collected_source_ids),
        "metadata": _normalize_metadata(
            payload.get("metadata")
        ),
    }


def _validate_findings(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ArtifactValidationError(
            "findings는 list여야 합니다."
        )

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        field_prefix = f"findings[{index}]"

        if not isinstance(item, dict):
            raise ArtifactValidationError(
                f"{field_prefix}는 dictionary여야 합니다."
            )

        topic = _require_string(
            item,
            "topic",
            minimum_length=1,
            field_prefix=field_prefix,
        )

        content = _require_string(
            item,
            "content",
            minimum_length=10,
            field_prefix=field_prefix,
        )

        importance = _normalize_choice(
            item.get("importance", "medium"),
            field_name=f"{field_prefix}.importance",
            allowed={"high", "medium", "low"},
            fallback="medium",
        )

        source_ids = _normalize_string_list(
            item.get("source_ids", []),
            field_name=f"{field_prefix}.source_ids",
        )

        normalized.append(
            {
                "topic": topic,
                "content": content,
                "importance": importance,
                "source_ids": source_ids,
                "is_inference": bool(
                    item.get("is_inference", False)
                ),
            }
        )

    return normalized


def _validate_evidence(
    value: Any,
) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ArtifactValidationError(
            "evidence는 list여야 합니다."
        )

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        field_prefix = f"evidence[{index}]"

        if not isinstance(item, dict):
            raise ArtifactValidationError(
                f"{field_prefix}는 dictionary여야 합니다."
            )

        claim = _require_string(
            item,
            "claim",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        support = _require_string(
            item,
            "support",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        source_id = str(
            item.get("source_id", "")
        ).strip()

        confidence = _normalize_choice(
            item.get("confidence", "medium"),
            field_name=f"{field_prefix}.confidence",
            allowed={"high", "medium", "low"},
            fallback="medium",
        )

        normalized.append(
            {
                "claim": claim,
                "support": support,
                "source_id": source_id,
                "confidence": confidence,
            }
        )

    return normalized


# =====================================================================
# Chapter Draft
# =====================================================================


def validate_chapter_draft(
    payload: dict[str, Any],
    *,
    minimum_markdown_length: int = 300,
) -> dict[str, Any]:
    """
    Writer가 생성한 CHAPTER_DRAFT를 검증하고 정규화한다.
    """

    if not isinstance(payload, dict):
        raise ArtifactValidationError(
            "Chapter Draft는 dictionary여야 합니다."
        )

    chapter_id = _require_chapter_id(payload)

    title = _require_string(
        payload,
        "title",
        minimum_length=1,
    )

    summary = _require_string(
        payload,
        "summary",
        minimum_length=10,
    )

    markdown = _require_string(
        payload,
        "markdown",
        minimum_length=minimum_markdown_length,
    )

    if not markdown.lstrip().startswith("#"):
        raise ArtifactValidationError(
            "Chapter Draft Markdown은 제목 헤딩으로 "
            "시작해야 합니다."
        )

    if markdown.count("```") % 2 != 0:
        raise ArtifactValidationError(
            "Chapter Draft의 Markdown 코드 블록이 "
            "정상적으로 닫히지 않았습니다."
        )

    if _has_abnormal_repetition(markdown):
        raise ArtifactValidationError(
            "Chapter Draft에서 비정상적인 반복이 "
            "감지되었습니다."
        )

    return {
        "artifact_type": "CHAPTER_DRAFT",
        "chapter_id": chapter_id,
        "title": title,
        "summary": summary,
        "markdown": markdown.strip(),
        "key_points": _normalize_string_list(
            payload.get("key_points", []),
            field_name="key_points",
        ),
        "source_ids": _normalize_string_list(
            payload.get("source_ids", []),
            field_name="source_ids",
        ),
        "metadata": _normalize_metadata(
            payload.get("metadata")
        ),
    }


# =====================================================================
# Review Artifact
# =====================================================================


def validate_review_artifact(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Reviewer 결과를 검증하고 REVIEW_ARTIFACT로 정규화한다.

    Review Artifact는 본문을 수정하지 않는다.
    본문의 문제와 수정 지침만 구조화한다.
    """

    if not isinstance(payload, dict):
        raise ArtifactValidationError(
            "Review Artifact는 dictionary여야 합니다."
        )

    chapter_id = _require_string(
        payload,
        "chapter_id",
        minimum_length=1,
    )

    title = _require_string(
        payload,
        "title",
        minimum_length=1,
    )

    overall_score = _normalize_integer(
        payload.get("overall_score"),
        field_name="overall_score",
        minimum=0,
        maximum=100,
    )

    verdict = _normalize_choice(
        payload.get("verdict"),
        field_name="verdict",
        allowed={
            "approved",
            "minor_revision",
            "major_revision",
            "rejected",
        },
        fallback="major_revision",
    )

    review_summary = _require_string(
        payload,
        "review_summary",
        minimum_length=20,
    )

    strengths = _normalize_string_list(
        payload.get("strengths", []),
        field_name="strengths",
    )

    issues = _validate_review_issues(
        payload.get("issues", [])
    )

    revision_instructions = _normalize_string_list(
        payload.get("revision_instructions", []),
        field_name="revision_instructions",
    )

    fact_check_items = _validate_fact_check_items(
        payload.get("fact_check_items", [])
    )

    missing_sections = _normalize_string_list(
        payload.get("missing_sections", []),
        field_name="missing_sections",
    )

    source_ids = _normalize_string_list(
        payload.get("source_ids", []),
        field_name="source_ids",
    )

    if verdict == "approved" and overall_score < 70:
        raise ArtifactValidationError(
            "approved 판정은 overall_score가 "
            "70 이상이어야 합니다."
        )

    if verdict in {
        "minor_revision",
        "major_revision",
        "rejected",
    } and not revision_instructions:
        raise ArtifactValidationError(
            f"verdict={verdict!r}인 경우 "
            "revision_instructions가 필요합니다."
        )

    if verdict in {
        "major_revision",
        "rejected",
    } and not issues:
        raise ArtifactValidationError(
            f"verdict={verdict!r}인 경우 "
            "issues가 최소 1개 이상 필요합니다."
        )

    return {
        "artifact_type": "REVIEW_ARTIFACT",
        "chapter_id": chapter_id,
        "title": title,
        "overall_score": overall_score,
        "verdict": verdict,
        "review_summary": review_summary,
        "strengths": strengths,
        "issues": issues,
        "revision_instructions": revision_instructions,
        "fact_check_items": fact_check_items,
        "missing_sections": missing_sections,
        "source_ids": source_ids,
        "metadata": _normalize_metadata(
            payload.get("metadata")
        ),
    }


def _validate_review_issues(
    value: Any,
) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ArtifactValidationError(
            "issues는 list여야 합니다."
        )

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        field_prefix = f"issues[{index}]"

        if not isinstance(item, dict):
            raise ArtifactValidationError(
                f"{field_prefix}는 dictionary여야 합니다."
            )

        category = _normalize_choice(
            item.get("category"),
            field_name=f"{field_prefix}.category",
            allowed={
                "accuracy",
                "completeness",
                "structure",
                "clarity",
                "style",
                "evidence",
                "consistency",
                "code",
                "other",
            },
            fallback="other",
        )

        severity = _normalize_choice(
            item.get("severity"),
            field_name=f"{field_prefix}.severity",
            allowed={
                "critical",
                "major",
                "minor",
                "suggestion",
            },
            fallback="minor",
        )

        description = _require_string(
            item,
            "description",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        recommendation = _require_string(
            item,
            "recommendation",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        location = str(
            item.get("location", "")
        ).strip()

        source_ids = _normalize_string_list(
            item.get("source_ids", []),
            field_name=f"{field_prefix}.source_ids",
        )

        normalized.append(
            {
                "category": category,
                "severity": severity,
                "location": location,
                "description": description,
                "recommendation": recommendation,
                "source_ids": source_ids,
            }
        )

    return normalized


def _validate_fact_check_items(
    value: Any,
) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ArtifactValidationError(
            "fact_check_items는 list여야 합니다."
        )

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        field_prefix = f"fact_check_items[{index}]"

        if not isinstance(item, dict):
            raise ArtifactValidationError(
                f"{field_prefix}는 dictionary여야 합니다."
            )

        claim = _require_string(
            item,
            "claim",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        status = _normalize_choice(
            item.get("status"),
            field_name=f"{field_prefix}.status",
            allowed={
                "supported",
                "partially_supported",
                "unsupported",
                "not_verifiable",
            },
            fallback="not_verifiable",
        )

        explanation = _require_string(
            item,
            "explanation",
            minimum_length=5,
            field_prefix=field_prefix,
        )

        source_ids = _normalize_string_list(
            item.get("source_ids", []),
            field_name=f"{field_prefix}.source_ids",
        )

        normalized.append(
            {
                "claim": claim,
                "status": status,
                "explanation": explanation,
                "source_ids": source_ids,
            }
        )

    return normalized


# =====================================================================
# Shared helpers
# =====================================================================


def _require_chapter_id(
    payload: dict[str, Any],
) -> str:
    value = (
        payload.get("chapter_id")
        or payload.get("unit_id")
        or payload.get("id")
        or ""
    )

    normalized = str(value).strip()

    if not normalized:
        raise ArtifactValidationError(
            "chapter_id가 필요합니다."
        )

    return normalized


def _require_string(
    payload: dict[str, Any],
    field_name: str,
    *,
    minimum_length: int,
    field_prefix: str | None = None,
) -> str:
    value = payload.get(field_name)

    display_name = (
        f"{field_prefix}.{field_name}"
        if field_prefix
        else field_name
    )

    if not isinstance(value, str):
        raise ArtifactValidationError(
            f"{display_name}는 문자열이어야 합니다."
        )

    normalized = value.strip()

    if len(normalized) < minimum_length:
        raise ArtifactValidationError(
            f"{display_name}가 너무 짧습니다. "
            f"length={len(normalized)}, "
            f"minimum={minimum_length}"
        )

    return normalized


def _normalize_string_list(
    value: Any,
    *,
    field_name: str,
) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ArtifactValidationError(
            f"{field_name}는 list여야 합니다."
        )

    normalized: list[str] = []

    for item in value:
        if not isinstance(item, str):
            continue

        text = item.strip()

        if text and text not in normalized:
            normalized.append(text)

    return normalized


def _normalize_choice(
    value: Any,
    *,
    field_name: str,
    allowed: set[str],
    fallback: str,
) -> str:
    normalized = str(value or "").strip().lower()

    if not normalized:
        return fallback

    if normalized not in allowed:
        raise ArtifactValidationError(
            f"{field_name} 값이 올바르지 않습니다. "
            f"allowed={sorted(allowed)}, "
            f"actual={normalized!r}"
        )

    return normalized


def _normalize_integer(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ArtifactValidationError(
            f"{field_name}는 정수여야 합니다."
        )

    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(
            f"{field_name}는 정수여야 합니다. "
            f"actual={value!r}"
        ) from exc

    if normalized < minimum or normalized > maximum:
        raise ArtifactValidationError(
            f"{field_name}는 {minimum} 이상 "
            f"{maximum} 이하여야 합니다. "
            f"actual={normalized}"
        )

    return normalized


def _normalize_metadata(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    return {}


def _has_abnormal_repetition(
    text: str,
) -> bool:
    repeated_pattern = re.compile(
        r"(.{15,100})\1{4,}",
        re.DOTALL,
    )

    return repeated_pattern.search(text) is not None
