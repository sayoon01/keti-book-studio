from __future__ import annotations

from typing import Any


def normalize_chapter_draft_revision(
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """
    구버전 CHAPTER_DRAFT에 revision metadata를 보완한다.

    원본 dictionary는 변경하지 않는다.

    정책:
    - Writer Draft는 revision=0으로 확정
    - 그 외(role 없음/reviser/editor 등)는 revision이
      없을 때만 1을 기본값으로 둔다
    - 이미 유효한 revision(>=0 int)이 있으면 유지
    """

    normalized = dict(artifact)

    if normalized.get(
        "artifact_type"
    ) != "CHAPTER_DRAFT":
        return normalized

    metadata = normalized.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    metadata = dict(metadata)

    revision = metadata.get("revision")

    if (
        isinstance(revision, int)
        and not isinstance(revision, bool)
        and revision >= 0
    ):
        normalized["metadata"] = metadata
        return normalized

    role = str(
        metadata.get("role", "")
    ).strip()

    if role == "writer":
        metadata["revision"] = 0
    else:
        # reviser/editor 등 다중 수정 이력이 있는
        # 구 Artifact는 정확한 번호를 알 수 없으므로
        # 누락 시에만 보수적으로 1을 넣는다.
        metadata.setdefault("revision", 1)

    normalized["metadata"] = metadata

    return normalized
