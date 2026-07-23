from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.adapters.chapter_draft_adapter import (
    normalize_chapter_draft_revision,
)
from backend.generation.chapter_generation_service import (
    _finalize_writer_draft,
)


def main() -> None:
    raw_payload = {
        "artifact_type": "WRONG_TYPE",
        "chapter_id": "wrong-id",
        "title": "",
        "summary": "테스트 요약",
        "markdown": (
            "# 테스트 챕터\n\n"
            "Writer가 생성한 본문입니다."
        ),
        "key_points": [
            "첫 번째 핵심"
        ],
        "source_ids": [
            "source-01"
        ],
        "metadata": {
            "model_field": "preserved",
            "revision": 99,
            "role": "wrong-role",
        },
    }

    result = _finalize_writer_draft(
        payload=raw_payload,
        chapter_id="chapter-writer-test",
        title="테스트 챕터",
        generation_metadata={
            "model": "fake-writer-model",
            "attempt": 1,
            "response_format": "markdown",
        },
    )

    assert result["artifact_type"] == (
        "CHAPTER_DRAFT"
    )

    assert result["chapter_id"] == (
        "chapter-writer-test"
    )

    assert result["title"] == "테스트 챕터"

    metadata = result["metadata"]

    assert metadata["role"] == "writer"
    assert metadata["stage"] == "writer"
    assert metadata["revision"] == 0
    assert metadata["model"] == (
        "fake-writer-model"
    )

    # 기존 비충돌 metadata는 보존
    assert metadata["model_field"] == (
        "preserved"
    )

    # Adapter: Writer 구버전 → revision=0
    legacy_writer = normalize_chapter_draft_revision(
        {
            "artifact_type": "CHAPTER_DRAFT",
            "metadata": {
                "role": "writer",
            },
        }
    )
    assert legacy_writer["metadata"][
        "revision"
    ] == 0

    # Adapter: revision 누락 비-Writer → setdefault 1
    legacy_other = normalize_chapter_draft_revision(
        {
            "artifact_type": "CHAPTER_DRAFT",
            "metadata": {
                "role": "reviser",
            },
        }
    )
    assert legacy_other["metadata"][
        "revision"
    ] == 1

    # Adapter: 이미 있는 revision은 유지
    legacy_kept = normalize_chapter_draft_revision(
        {
            "artifact_type": "CHAPTER_DRAFT",
            "metadata": {
                "role": "reviser",
                "revision": 3,
            },
        }
    )
    assert legacy_kept["metadata"][
        "revision"
    ] == 3

    print("=" * 72)
    print("WRITER REVISION TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        result["artifact_type"],
    )
    print(
        "chapter_id=",
        result["chapter_id"],
    )
    print(
        "role=",
        metadata["role"],
    )
    print(
        "stage=",
        metadata["stage"],
    )
    print(
        "revision=",
        metadata["revision"],
    )
    print()
    print("PASS: Writer canonical artifact type")
    print("PASS: Writer canonical chapter ID")
    print("PASS: Writer role metadata")
    print("PASS: Writer initial revision")
    print("PASS: Generation metadata preservation")
    print("PASS: Legacy Writer revision adapter")
    print("PASS: Legacy non-Writer revision default")
    print("PASS: Existing revision preservation")


if __name__ == "__main__":
    main()
