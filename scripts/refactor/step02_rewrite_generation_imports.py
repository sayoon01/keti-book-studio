from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SEARCH_ROOTS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "tests",
]

REPLACEMENTS = {
    "backend.orchestration.chapter_llm_service": (
        "backend.generation.chapter_generation_service"
    ),
    "backend.orchestration.artifact_payloads": (
        "backend.generation.validators.artifact_payloads"
    ),
    "backend.orchestration.prompts": (
        "backend.generation.prompts"
    ),
    "backend.llm.ollama_json_client": (
        "backend.infrastructure.llm.ollama_json_client"
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
