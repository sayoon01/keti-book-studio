from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"

OLD_AGENTS = BACKEND / "agents"
ORCHESTRATION = BACKEND / "orchestration"
STAGES = ORCHESTRATION / "stages"


MOVE_MAP = {
    OLD_AGENTS / "base.py": STAGES / "base.py",
    OLD_AGENTS / "registry.py": STAGES / "registry.py",

    OLD_AGENTS / "context.py": ORCHESTRATION / "context.py",
    OLD_AGENTS / "context_builder.py": (
        ORCHESTRATION / "context_builder.py"
    ),
    OLD_AGENTS / "schemas.py": (
        ORCHESTRATION / "agent_schemas.py"
    ),

    OLD_AGENTS / "planner.py": (
        STAGES / "planner_stage.py"
    ),
    OLD_AGENTS / "researcher.py": (
        STAGES / "researcher_stage.py"
    ),
    OLD_AGENTS / "writer.py": (
        STAGES / "writer_stage.py"
    ),
    OLD_AGENTS / "reviewer.py": (
        STAGES / "reviewer_stage.py"
    ),
    OLD_AGENTS / "editor.py": (
        STAGES / "editor_stage.py"
    ),
    OLD_AGENTS / "reviser.py": (
        STAGES / "reviser_stage.py"
    ),
    OLD_AGENTS / "reader.py": (
        STAGES / "reader_stage.py"
    ),
    OLD_AGENTS / "finalizer.py": (
        STAGES / "finalizer_stage.py"
    ),
}


def move_file(source: Path, destination: Path) -> None:
    if destination.exists():
        print(f"[SKIP] destination exists: {destination}")
        return

    if not source.exists():
        print(f"[SKIP] source missing: {source}")
        return

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.move(
        str(source),
        str(destination),
    )

    print(
        f"[MOVE] "
        f"{source.relative_to(PROJECT_ROOT)} "
        f"-> {destination.relative_to(PROJECT_ROOT)}"
    )


def ensure_init_file(path: Path) -> None:
    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    init_file = path / "__init__.py"

    if not init_file.exists():
        init_file.write_text(
            '"""Package initialization."""\n',
            encoding="utf-8",
        )

        print(
            f"[CREATE] "
            f"{init_file.relative_to(PROJECT_ROOT)}"
        )


def main() -> None:
    if not OLD_AGENTS.exists():
        raise RuntimeError(
            f"기존 Agent 디렉터리가 없습니다: {OLD_AGENTS}"
        )

    ensure_init_file(ORCHESTRATION)
    ensure_init_file(STAGES)

    for source, destination in MOVE_MAP.items():
        move_file(
            source,
            destination,
        )

    print()
    print("Production Agent 파일 이동 완료")
    print("아직 import 수정과 호환 모듈 생성이 필요합니다.")


if __name__ == "__main__":
    main()
