from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"

ORCHESTRATION = BACKEND / "orchestration"
OLD_LLM = BACKEND / "llm"

GENERATION = BACKEND / "generation"
GENERATION_PROMPTS = GENERATION / "prompts"
GENERATION_VALIDATORS = GENERATION / "validators"

INFRASTRUCTURE = BACKEND / "infrastructure"
INFRASTRUCTURE_LLM = INFRASTRUCTURE / "llm"


DIRECT_FILE_MOVES = {
    ORCHESTRATION / "chapter_llm_service.py": (
        GENERATION / "chapter_generation_service.py"
    ),
    ORCHESTRATION / "artifact_payloads.py": (
        GENERATION_VALIDATORS / "artifact_payloads.py"
    ),
    OLD_LLM / "ollama_json_client.py": (
        INFRASTRUCTURE_LLM / "ollama_json_client.py"
    ),
}


def ensure_package(path: Path) -> None:
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
            "[CREATE]",
            init_file.relative_to(PROJECT_ROOT),
        )


def move_file(
    source: Path,
    destination: Path,
) -> None:
    if destination.exists():
        print(
            "[SKIP] destination exists:",
            destination.relative_to(PROJECT_ROOT),
        )
        return

    if not source.exists():
        print(
            "[SKIP] source missing:",
            source.relative_to(PROJECT_ROOT),
        )
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
        "[MOVE]",
        source.relative_to(PROJECT_ROOT),
        "->",
        destination.relative_to(PROJECT_ROOT),
    )


def move_prompts() -> None:
    old_prompts = ORCHESTRATION / "prompts"

    if not old_prompts.exists():
        print(
            "[SKIP] prompt directory missing:",
            old_prompts.relative_to(PROJECT_ROOT),
        )
        return

    for source in sorted(old_prompts.glob("*.py")):
        if source.name == "__init__.py":
            continue

        destination = (
            GENERATION_PROMPTS
            / source.name
        )

        move_file(
            source,
            destination,
        )


def main() -> None:
    for package in [
        GENERATION,
        GENERATION_PROMPTS,
        GENERATION_VALIDATORS,
        INFRASTRUCTURE,
        INFRASTRUCTURE_LLM,
    ]:
        ensure_package(package)

    for source, destination in DIRECT_FILE_MOVES.items():
        move_file(
            source,
            destination,
        )

    move_prompts()

    print()
    print("Generation 계층 파일 이동 완료")
    print("다음으로 import 경로를 수정해야 합니다.")


if __name__ == "__main__":
    main()
