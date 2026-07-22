from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGES = (
    PROJECT_ROOT
    / "backend"
    / "orchestration"
    / "stages"
)

REPLACEMENTS = {
    "from .context import ": (
        "from backend.orchestration.context import "
    ),
    "from .context_builder import ": (
        "from backend.orchestration.context_builder import "
    ),
    "from .schemas import ": (
        "from backend.orchestration.agent_schemas import "
    ),
    "from ..context import ": (
        "from backend.orchestration.context import "
    ),
    "from ..context_builder import ": (
        "from backend.orchestration.context_builder import "
    ),
    "from ..schemas import ": (
        "from backend.orchestration.agent_schemas import "
    ),
    "from .planner import ": (
        "from backend.orchestration.stages.planner_stage import "
    ),
    "from .researcher import ": (
        "from backend.orchestration.stages.researcher_stage import "
    ),
    "from .writer import ": (
        "from backend.orchestration.stages.writer_stage import "
    ),
    "from .reviewer import ": (
        "from backend.orchestration.stages.reviewer_stage import "
    ),
    "from .editor import ": (
        "from backend.orchestration.stages.editor_stage import "
    ),
    "from .reviser import ": (
        "from backend.orchestration.stages.reviser_stage import "
    ),
    "from .reader import ": (
        "from backend.orchestration.stages.reader_stage import "
    ),
    "from .finalizer import ": (
        "from backend.orchestration.stages.finalizer_stage import "
    ),
}


def main() -> None:
    changed = []

    for path in STAGES.rglob("*.py"):
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
            continue

        path.write_text(
            updated,
            encoding="utf-8",
        )

        changed.append(path)

    print(
        f"수정된 Stage 파일 수: {len(changed)}"
    )

    for path in changed:
        print(
            "[UPDATE]",
            path.relative_to(PROJECT_ROOT),
        )


if __name__ == "__main__":
    main()
