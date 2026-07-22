from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SEARCH_ROOTS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "tests",
]

REPLACEMENTS = {
    "backend.agents.base": (
        "backend.orchestration.stages.base"
    ),
    "backend.agents.registry": (
        "backend.orchestration.stages.registry"
    ),
    "backend.agents.context_builder": (
        "backend.orchestration.context_builder"
    ),
    "backend.agents.context": (
        "backend.orchestration.context"
    ),
    "backend.agents.schemas": (
        "backend.orchestration.agent_schemas"
    ),
    "backend.agents.planner": (
        "backend.orchestration.stages.planner_stage"
    ),
    "backend.agents.researcher": (
        "backend.orchestration.stages.researcher_stage"
    ),
    "backend.agents.writer": (
        "backend.orchestration.stages.writer_stage"
    ),
    "backend.agents.reviewer": (
        "backend.orchestration.stages.reviewer_stage"
    ),
    "backend.agents.editor": (
        "backend.orchestration.stages.editor_stage"
    ),
    "backend.agents.reviser": (
        "backend.orchestration.stages.reviser_stage"
    ),
    "backend.agents.reader": (
        "backend.orchestration.stages.reader_stage"
    ),
    "backend.agents.finalizer": (
        "backend.orchestration.stages.finalizer_stage"
    ),
}


def rewrite_file(path: Path) -> bool:
    original = path.read_text(
        encoding="utf-8",
    )

    updated = original

    for old, new in REPLACEMENTS.items():
        updated = updated.replace(
            old,
            new,
        )

    if updated == original:
        return False

    path.write_text(
        updated,
        encoding="utf-8",
    )

    return True


def main() -> None:
    changed_files: list[Path] = []

    for search_root in SEARCH_ROOTS:
        if not search_root.exists():
            continue

        for path in search_root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue

            if rewrite_file(path):
                changed_files.append(path)

    print(
        f"수정된 파일 수: {len(changed_files)}"
    )

    for path in changed_files:
        print(
            "[UPDATE]",
            path.relative_to(PROJECT_ROOT),
        )


if __name__ == "__main__":
    main()
