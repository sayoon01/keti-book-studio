from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.schemas import (
    EditorMode,
    EditorScope,
    parse_editor_command,
)


def main() -> None:
    markdown = """
# 테스트 챕터

## 첫 번째 섹션

이 문장은 편집할 테스트 문장입니다.

## 두 번째 섹션

두 번째 섹션의 내용입니다.
""".strip()

    selected_text = (
        "이 문장은 편집할 테스트 문장입니다."
    )

    start = markdown.index(selected_text)
    end = start + len(selected_text)

    selection_command = parse_editor_command(
        {
            "mode": "rewrite",
            "scope": "selection",
            "instruction": (
                "더 자연스럽게 작성하세요."
            ),
            "selection": {
                "start": start,
                "end": end,
                "text": selected_text,
            },
        },
        chapter_markdown=markdown,
    )

    assert selection_command.mode == (
        EditorMode.REWRITE
    )

    assert selection_command.scope == (
        EditorScope.SELECTION
    )

    assert selection_command.selection is not None
    assert selection_command.selection.start == start
    assert selection_command.selection.end == end

    chapter_command = parse_editor_command(
        {
            "mode": "professional",
            "scope": "chapter",
            "instruction": "",
        },
        chapter_markdown=markdown,
    )

    assert chapter_command.mode == (
        EditorMode.PROFESSIONAL
    )

    assert chapter_command.scope == (
        EditorScope.CHAPTER
    )

    assert chapter_command.selection is None

    print("=" * 72)
    print("EDITOR COMMAND TEST")
    print("=" * 72)
    print(
        "selection_mode=",
        selection_command.mode.value,
    )
    print(
        "selection_scope=",
        selection_command.scope.value,
    )
    print(
        "selection_start=",
        selection_command.selection.start,
    )
    print(
        "selection_end=",
        selection_command.selection.end,
    )
    print(
        "chapter_mode=",
        chapter_command.mode.value,
    )
    print(
        "chapter_scope=",
        chapter_command.scope.value,
    )
    print()
    print("PASS: Editor command parsing")
    print("PASS: Chapter scope validation")
    print("PASS: Selection scope validation")
    print("PASS: Selection range validation")


if __name__ == "__main__":
    main()
