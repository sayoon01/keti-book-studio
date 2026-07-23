from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EditorCommandValidationError(ValueError):
    """
    Editor 명령이 잘못된 경우 발생한다.
    """


class EditorMode(str, Enum):
    """
    Editor가 지원하는 편집 방식.
    """

    REWRITE = "rewrite"
    EXPAND = "expand"
    SUMMARIZE = "summarize"
    SIMPLIFY = "simplify"
    PROFESSIONAL = "professional"
    PROOFREAD = "proofread"
    TABLE = "table"
    CUSTOM = "custom"


class EditorScope(str, Enum):
    """
    편집 범위.
    """

    CHAPTER = "chapter"
    SELECTION = "selection"


@dataclass(frozen=True, slots=True)
class EditorSelection:
    """
    챕터에서 사용자가 선택한 Markdown 영역.

    start와 end는 Python 문자열 슬라이스 기준이다.

    예:
        selected = markdown[start:end]
    """

    start: int
    end: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class EditorCommand:
    """
    Editor 실행을 위한 정본 명령 객체.
    """

    mode: EditorMode
    scope: EditorScope
    instruction: str
    selection: EditorSelection | None = None
    preserve_markdown_structure: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "scope": self.scope.value,
            "instruction": self.instruction,
            "selection": (
                self.selection.to_dict()
                if self.selection is not None
                else None
            ),
            "preserve_markdown_structure": (
                self.preserve_markdown_structure
            ),
        }


def parse_editor_command(
    value: EditorCommand | dict[str, Any],
    *,
    chapter_markdown: str,
) -> EditorCommand:
    """
    EditorCommand 객체 또는 dictionary를 검증하고
    정본 EditorCommand로 변환한다.
    """

    if isinstance(value, EditorCommand):
        command = value
    elif isinstance(value, dict):
        command = _parse_editor_command_dict(
            value
        )
    else:
        raise EditorCommandValidationError(
            "editor_command는 EditorCommand 또는 "
            "dictionary여야 합니다."
        )

    validate_editor_command(
        command,
        chapter_markdown=chapter_markdown,
    )

    return command


def validate_editor_command(
    command: EditorCommand,
    *,
    chapter_markdown: str,
) -> None:
    """
    Editor 명령과 챕터 본문의 일관성을 검증한다.
    """

    if not isinstance(command.mode, EditorMode):
        raise EditorCommandValidationError(
            "command.mode는 EditorMode여야 합니다."
        )

    if not isinstance(command.scope, EditorScope):
        raise EditorCommandValidationError(
            "command.scope는 EditorScope여야 합니다."
        )

    instruction = command.instruction.strip()

    if (
        command.mode == EditorMode.CUSTOM
        and not instruction
    ):
        raise EditorCommandValidationError(
            "custom 모드에는 instruction이 필요합니다."
        )

    if not isinstance(chapter_markdown, str):
        raise EditorCommandValidationError(
            "chapter_markdown은 문자열이어야 합니다."
        )

    if not chapter_markdown.strip():
        raise EditorCommandValidationError(
            "편집할 chapter_markdown이 비어 있습니다."
        )

    if command.scope == EditorScope.CHAPTER:
        if command.selection is not None:
            raise EditorCommandValidationError(
                "chapter 범위에서는 selection을 "
                "지정할 수 없습니다."
            )

        return

    if command.selection is None:
        raise EditorCommandValidationError(
            "selection 범위에서는 selection 정보가 "
            "필요합니다."
        )

    selection = command.selection

    if selection.start < 0:
        raise EditorCommandValidationError(
            "selection.start는 0 이상이어야 합니다."
        )

    if selection.end <= selection.start:
        raise EditorCommandValidationError(
            "selection.end는 selection.start보다 "
            "커야 합니다."
        )

    if selection.end > len(chapter_markdown):
        raise EditorCommandValidationError(
            "selection.end가 Markdown 길이를 "
            "초과했습니다. "
            f"end={selection.end}, "
            f"length={len(chapter_markdown)}"
        )

    actual_text = chapter_markdown[
        selection.start:selection.end
    ]

    if actual_text != selection.text:
        raise EditorCommandValidationError(
            "selection.text와 실제 Markdown 선택 영역이 "
            "일치하지 않습니다."
        )

    if not selection.text.strip():
        raise EditorCommandValidationError(
            "selection.text가 비어 있습니다."
        )


def get_default_editor_instruction(
    mode: EditorMode,
) -> str:
    """
    Mode별 기본 편집 지침.
    """

    instructions = {
        EditorMode.REWRITE: (
            "핵심 의미는 유지하면서 문장을 자연스럽고 "
            "명확하게 다시 작성하세요."
        ),
        EditorMode.EXPAND: (
            "기존 의미를 유지하면서 필요한 설명과 예시를 "
            "추가하여 내용을 확장하세요."
        ),
        EditorMode.SUMMARIZE: (
            "핵심 정보와 논리 구조를 유지하면서 내용을 "
            "더 짧고 간결하게 요약하세요."
        ),
        EditorMode.SIMPLIFY: (
            "전문 용어를 쉽게 풀어 설명하고 초보자도 "
            "이해할 수 있는 문장으로 바꾸세요."
        ),
        EditorMode.PROFESSIONAL: (
            "내용의 의미를 유지하면서 전문 기술 문서에 "
            "적합한 문체로 수정하세요."
        ),
        EditorMode.PROOFREAD: (
            "맞춤법, 띄어쓰기, 문법, 어색한 표현을 "
            "교정하되 내용은 변경하지 마세요."
        ),
        EditorMode.TABLE: (
            "선택된 내용을 정보 손실 없이 적절한 "
            "Markdown 표로 변환하세요."
        ),
        EditorMode.CUSTOM: "",
    }

    return instructions[mode]


def _parse_editor_command_dict(
    value: dict[str, Any],
) -> EditorCommand:
    mode_value = str(
        value.get("mode", "")
    ).strip().lower()

    scope_value = str(
        value.get("scope", "chapter")
    ).strip().lower()

    try:
        mode = EditorMode(mode_value)
    except ValueError as exc:
        raise EditorCommandValidationError(
            "지원하지 않는 Editor mode입니다. "
            f"actual={mode_value!r}, "
            f"allowed={[item.value for item in EditorMode]}"
        ) from exc

    try:
        scope = EditorScope(scope_value)
    except ValueError as exc:
        raise EditorCommandValidationError(
            "지원하지 않는 Editor scope입니다. "
            f"actual={scope_value!r}, "
            f"allowed={[item.value for item in EditorScope]}"
        ) from exc

    instruction = str(
        value.get("instruction", "")
    ).strip()

    selection_value = value.get("selection")
    selection: EditorSelection | None = None

    if selection_value is not None:
        if not isinstance(selection_value, dict):
            raise EditorCommandValidationError(
                "selection은 dictionary여야 합니다."
            )

        start = selection_value.get("start")
        end = selection_value.get("end")
        text = selection_value.get("text")

        if (
            not isinstance(start, int)
            or isinstance(start, bool)
        ):
            raise EditorCommandValidationError(
                "selection.start는 정수여야 합니다."
            )

        if (
            not isinstance(end, int)
            or isinstance(end, bool)
        ):
            raise EditorCommandValidationError(
                "selection.end는 정수여야 합니다."
            )

        if not isinstance(text, str):
            raise EditorCommandValidationError(
                "selection.text는 문자열이어야 합니다."
            )

        selection = EditorSelection(
            start=start,
            end=end,
            text=text,
        )

    preserve_markdown_structure = value.get(
        "preserve_markdown_structure",
        True,
    )

    if not isinstance(
        preserve_markdown_structure,
        bool,
    ):
        raise EditorCommandValidationError(
            "preserve_markdown_structure는 "
            "boolean이어야 합니다."
        )

    return EditorCommand(
        mode=mode,
        scope=scope,
        instruction=instruction,
        selection=selection,
        preserve_markdown_structure=(
            preserve_markdown_structure
        ),
    )
