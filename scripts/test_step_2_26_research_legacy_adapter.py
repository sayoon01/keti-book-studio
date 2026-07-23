from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.adapters import (
    to_legacy_research_payload,
)


def main() -> None:
    canonical = {
        "artifact_type": "RESEARCH_ARTIFACT",
        "chapter_id": "chapter-01",
        "title": "테스트 챕터",
        "research_summary": (
            "정본 Research Artifact의 조사 요약입니다."
        ),
        "findings": [
            {
                "topic": "첫 번째 핵심",
                "content": "첫 번째 조사 내용입니다.",
                "importance": "high",
                "source_ids": ["source-01"],
                "is_inference": False,
            },
            {
                "topic": "두 번째 핵심",
                "content": "두 번째 조사 내용입니다.",
                "importance": "medium",
                "source_ids": ["source-02"],
                "is_inference": False,
            },
        ],
        "evidence": [],
        "writing_guidance": [
            "핵심 내용을 순서대로 설명한다."
        ],
        "required_sections": [],
        "gaps": [],
        "source_ids": [
            "source-01",
            "source-02",
        ],
        "metadata": {},
    }

    legacy = to_legacy_research_payload(
        canonical
    )

    assert "summary" not in canonical
    assert "key_points" not in canonical

    assert legacy["summary"] == (
        canonical["research_summary"]
    )

    assert legacy["key_points"] == [
        "첫 번째 핵심",
        "두 번째 핵심",
    ]

    assert legacy is not canonical

    print("=" * 72)
    print("RESEARCH LEGACY ADAPTER")
    print("=" * 72)
    print("canonical_has_summary=", "summary" in canonical)
    print("legacy_has_summary=", "summary" in legacy)
    print("legacy_key_points=", legacy["key_points"])
    print()
    print("PASS: Canonical artifact unchanged")
    print("PASS: Legacy fields added at adapter boundary")


if __name__ == "__main__":
    main()
