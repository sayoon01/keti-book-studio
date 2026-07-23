from __future__ import annotations

from typing import Any


def to_legacy_research_payload(
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """
    정본 RESEARCH_ARTIFACT를 구 코드가 사용하던 형태로 변환한다.

    새 Generation/Orchestration 경로에서는 사용하지 않는다.

    사용 가능한 경계:
    - 아직 마이그레이션하지 못한 API
    - 예전 agents 패키지
    - 이전 테스트 코드
    - 기존 저장 데이터 변환

    정본 Artifact 자체는 수정하지 않고 복사본을 반환한다.
    """

    if not isinstance(artifact, dict):
        raise TypeError(
            "artifact는 dictionary여야 합니다."
        )

    artifact_type = str(
        artifact.get("artifact_type", "")
    ).strip()

    if artifact_type != "RESEARCH_ARTIFACT":
        raise ValueError(
            "RESEARCH_ARTIFACT만 Legacy Research Payload로 "
            "변환할 수 있습니다. "
            f"actual={artifact_type!r}"
        )

    result = dict(artifact)

    research_summary = str(
        result.get("research_summary", "")
    ).strip()

    result["summary"] = research_summary
    result["key_points"] = _extract_key_points(
        result.get("findings", [])
    )

    return result


def _extract_key_points(
    findings: Any,
) -> list[str]:
    if not isinstance(findings, list):
        return []

    key_points: list[str] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        topic = str(
            finding.get("topic", "")
        ).strip()

        if topic and topic not in key_points:
            key_points.append(topic)

    return key_points
