from __future__ import annotations

import json
from typing import Any, Iterable


class ArtifactContentError(ValueError):
    pass


def parse_artifact_content(
    artifact: Any,
) -> dict[str, Any]:
    raw_content = getattr(artifact, "content", None)

    if raw_content is None:
        raw_content = getattr(
            artifact,
            "content_json",
            None,
        )

    if isinstance(raw_content, dict):
        return raw_content

    if not isinstance(raw_content, str):
        raise ArtifactContentError(
            "Artifact content가 문자열 또는 dict가 아닙니다. "
            f"artifact_id={getattr(artifact, 'artifact_id', None)}"
        )

    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ArtifactContentError(
            "Artifact content_json 파싱에 실패했습니다. "
            f"artifact_id={getattr(artifact, 'artifact_id', None)}"
        ) from exc

    if not isinstance(payload, dict):
        raise ArtifactContentError(
            "Artifact content 최상위 값은 dict여야 합니다. "
            f"artifact_id={getattr(artifact, 'artifact_id', None)}"
        )

    return payload


def index_artifacts_by_type(
    artifacts: Iterable[Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for artifact in artifacts:
        artifact_type = getattr(
            artifact,
            "artifact_type",
            None,
        )

        if not artifact_type:
            continue

        result[str(artifact_type)] = artifact

    return result


def get_artifact_payload(
    artifacts_by_type: dict[str, Any],
    artifact_type: str,
) -> dict[str, Any]:
    artifact = artifacts_by_type.get(artifact_type)

    if artifact is None:
        raise ArtifactContentError(
            f"필수 Artifact가 없습니다: {artifact_type}"
        )

    return parse_artifact_content(artifact)
