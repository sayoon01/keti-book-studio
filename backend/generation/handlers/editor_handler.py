from __future__ import annotations

import logging
import re
from typing import Any

from backend.generation.handlers.base_text_handler import (
    BaseTextHandler,
    TextExecutionContext,
    TextPromptBundleProtocol,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_editor import (
    build_chapter_editor_prompts,
)
from backend.generation.schemas import (
    EditorCommand,
    EditorCommandValidationError,
    EditorScope,
    parse_editor_command,
)
from backend.generation.validators import (
    validate_chapter_draft,
)
from backend.infrastructure.llm import OllamaClient


logger = logging.getLogger(__name__)


class EditorHandler(
    BaseTextHandler[dict[str, Any]]
):
    """
    사용자 명령에 따라 챕터 전체 또는 선택 영역을 편집한다.
    """

    role = GenerationRole.EDITOR
    operation_name = "Chapter Editor"

    def __init__(
        self,
        *,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        super().__init__(
            client=client,
            model_router=model_router,
            max_attempts=max_attempts,
        )

    async def run(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        chapter_draft: dict[str, Any],
        editor_command: EditorCommand | dict[str, Any],
        research_artifact: dict[str, Any] | None = None,
        review_artifact: dict[str, Any] | None = None,
        previous_chapters: list[dict[str, Any]] | None = None,
        revision_number: int | None = None,
    ) -> dict[str, Any]:
        """
        사용자 명령을 반영한 새로운 CHAPTER_DRAFT를 반환한다.
        """

        markdown = str(
            chapter_draft.get("markdown", "")
        )

        parsed_command = parse_editor_command(
            editor_command,
            chapter_markdown=markdown,
        )

        resolved_revision = (
            revision_number
            if revision_number is not None
            else _resolve_next_revision(
                chapter_draft
            )
        )

        return await self._execute(
            book_config=book_config,
            chapter_plan=chapter_plan,
            chapter_draft=chapter_draft,
            editor_command=parsed_command,
            research_artifact=research_artifact,
            review_artifact=review_artifact,
            previous_chapters=previous_chapters or [],
            revision_number=resolved_revision,
        )

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        book_config = inputs.get("book_config")
        chapter_plan = inputs.get("chapter_plan")
        chapter_draft = inputs.get(
            "chapter_draft"
        )
        editor_command = inputs.get(
            "editor_command"
        )
        previous_chapters = inputs.get(
            "previous_chapters"
        )
        revision_number = inputs.get(
            "revision_number"
        )

        if not isinstance(book_config, dict):
            raise TypeError(
                "book_config는 dictionary여야 합니다."
            )

        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "chapter_plan은 dictionary여야 합니다."
            )

        if not isinstance(chapter_draft, dict):
            raise TypeError(
                "chapter_draft는 dictionary여야 합니다."
            )

        if chapter_draft.get(
            "artifact_type"
        ) != "CHAPTER_DRAFT":
            raise ValueError(
                "Editor에는 CHAPTER_DRAFT가 필요합니다. "
                f"actual={chapter_draft.get('artifact_type')!r}"
            )

        if not isinstance(
            editor_command,
            EditorCommand,
        ):
            raise TypeError(
                "editor_command는 EditorCommand여야 합니다."
            )

        if not isinstance(
            previous_chapters,
            list,
        ):
            raise TypeError(
                "previous_chapters는 list여야 합니다."
            )

        if (
            not isinstance(revision_number, int)
            or isinstance(revision_number, bool)
            or revision_number <= 0
        ):
            raise ValueError(
                "revision_number는 1 이상의 정수여야 합니다."
            )

        markdown = chapter_draft.get("markdown")

        if (
            not isinstance(markdown, str)
            or not markdown.strip()
        ):
            raise ValueError(
                "chapter_draft.markdown이 비어 있습니다."
            )

        draft_chapter_id = _get_chapter_id(
            chapter_draft
        )

        plan_chapter_id = _get_chapter_id(
            chapter_plan
        )

        if not draft_chapter_id:
            raise ValueError(
                "chapter_draft.chapter_id가 필요합니다."
            )

        if (
            plan_chapter_id
            and plan_chapter_id
            != draft_chapter_id
        ):
            raise ValueError(
                "chapter_plan과 chapter_draft의 "
                "chapter_id가 일치하지 않습니다."
            )

    def _build_prompts(
        self,
        **inputs: Any,
    ) -> TextPromptBundleProtocol:
        return build_chapter_editor_prompts(
            book_config=inputs["book_config"],
            chapter_plan=inputs["chapter_plan"],
            chapter_draft=inputs["chapter_draft"],
            editor_command=inputs["editor_command"],
            research_artifact=inputs[
                "research_artifact"
            ],
            review_artifact=inputs[
                "review_artifact"
            ],
            previous_chapters=inputs[
                "previous_chapters"
            ],
        )

    def _get_minimum_length(
        self,
        **inputs: Any,
    ) -> int:
        editor_command = inputs.get(
            "editor_command"
        )

        if (
            isinstance(editor_command, EditorCommand)
            and editor_command.scope
            == EditorScope.SELECTION
        ):
            return 1

        return 300

    def _clean_generated_text(
        self,
        text: str,
    ) -> str:
        cleaned = super()._clean_generated_text(
            text
        )

        explanation_prefixes = (
            "수정된 내용은 다음과 같습니다.",
            "수정 결과:",
            "편집 결과:",
            "다음과 같이 수정했습니다.",
        )

        for prefix in explanation_prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[
                    len(prefix):
                ].lstrip()

        return cleaned.strip()

    def _build_artifact(
        self,
        *,
        generated_text: str,
        execution_context: TextExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        chapter_plan = inputs["chapter_plan"]
        chapter_draft = inputs["chapter_draft"]
        editor_command = inputs["editor_command"]
        revision_number = inputs[
            "revision_number"
        ]

        original_markdown = str(
            chapter_draft.get("markdown", "")
        )

        if editor_command.scope == EditorScope.CHAPTER:
            edited_markdown = _normalize_full_chapter(
                generated_text=generated_text,
                original_title=str(
                    chapter_draft.get("title", "")
                ).strip(),
            )
        else:
            selection = editor_command.selection

            if selection is None:
                raise EditorCommandValidationError(
                    "selection 편집 결과를 조립할 수 없습니다."
                )

            edited_selection = (
                _normalize_selection_output(
                    generated_text
                )
            )

            edited_markdown = (
                original_markdown[:selection.start]
                + edited_selection
                + original_markdown[selection.end:]
            )

        title = (
            _extract_markdown_title(
                edited_markdown
            )
            or str(
                chapter_draft.get("title")
                or chapter_plan.get("title")
                or ""
            ).strip()
        )

        source_ids = _merge_string_lists(
            chapter_draft.get(
                "source_ids",
                [],
            ),
            _get_source_ids(
                inputs.get("research_artifact")
            ),
            _get_source_ids(
                inputs.get("review_artifact")
            ),
        )

        key_points = _resolve_key_points(
            chapter_plan=chapter_plan,
            chapter_draft=chapter_draft,
        )

        previous_metadata = chapter_draft.get(
            "metadata",
            {},
        )

        if not isinstance(previous_metadata, dict):
            previous_metadata = {}

        metadata = {
            **self._build_metadata(
                execution_context
            ),
            "stage": "editor",
            "revision": revision_number,
            "edit_mode": editor_command.mode.value,
            "edit_scope": editor_command.scope.value,
            "user_instruction": (
                editor_command.instruction
            ),
            "selection_start": (
                editor_command.selection.start
                if editor_command.selection is not None
                else None
            ),
            "selection_end": (
                editor_command.selection.end
                if editor_command.selection is not None
                else None
            ),
            "previous_role": previous_metadata.get(
                "role"
            ),
            "previous_revision": (
                previous_metadata.get("revision")
            ),
        }

        payload = {
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": _get_chapter_id(
                chapter_draft
            ),
            "title": title,
            "summary": _build_edited_summary(
                chapter_draft=chapter_draft,
                editor_command=editor_command,
            ),
            "markdown": edited_markdown,
            "key_points": key_points,
            "source_ids": source_ids,
            "metadata": metadata,
        }

        return validate_chapter_draft(
            payload,
            minimum_markdown_length=100,
        )

    def _log_completion(
        self,
        *,
        artifact: dict[str, Any],
        execution_context: TextExecutionContext,
    ) -> None:
        metadata = artifact.get(
            "metadata",
            {},
        )

        logger.info(
            "%s completed: chapter_id=%s model=%s "
            "attempt=%s revision=%s mode=%s scope=%s "
            "markdown_length=%s",
            self.operation_name,
            artifact.get("chapter_id"),
            execution_context.model,
            execution_context.attempt,
            metadata.get("revision"),
            metadata.get("edit_mode"),
            metadata.get("edit_scope"),
            len(
                str(
                    artifact.get(
                        "markdown",
                        "",
                    )
                )
            ),
        )


def _normalize_full_chapter(
    *,
    generated_text: str,
    original_title: str,
) -> str:
    cleaned = generated_text.strip()

    first_h1 = re.search(
        r"(?m)^#\s+.+$",
        cleaned,
    )

    if first_h1 is not None:
        return cleaned[first_h1.start():].strip()

    if original_title:
        return (
            f"# {original_title}\n\n"
            f"{cleaned}"
        ).strip()

    raise ValueError(
        "전체 챕터 편집 결과에 H1 제목이 없으며 "
        "기존 제목도 확인할 수 없습니다."
    )


def _normalize_selection_output(
    generated_text: str,
) -> str:
    cleaned = generated_text.strip()

    if not cleaned:
        raise ValueError(
            "선택 영역 편집 결과가 비어 있습니다."
        )

    return cleaned


def _extract_markdown_title(
    markdown: str,
) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            return stripped[2:].strip()

    return ""


def _get_chapter_id(
    payload: dict[str, Any],
) -> str:
    value = (
        payload.get("chapter_id")
        or payload.get("unit_id")
        or payload.get("id")
        or ""
    )

    return str(value).strip()


def _resolve_next_revision(
    chapter_draft: dict[str, Any],
) -> int:
    metadata = chapter_draft.get(
        "metadata",
        {},
    )

    if not isinstance(metadata, dict):
        return 1

    current_revision = metadata.get(
        "revision"
    )

    if (
        isinstance(current_revision, int)
        and not isinstance(current_revision, bool)
        and current_revision >= 0
    ):
        return current_revision + 1

    return 1


def _build_edited_summary(
    *,
    chapter_draft: dict[str, Any],
    editor_command: EditorCommand,
) -> str:
    original_summary = str(
        chapter_draft.get(
            "summary",
            "",
        )
    ).strip()

    mode = editor_command.mode.value
    scope = editor_command.scope.value

    suffix = (
        f"Editor의 {mode} 명령을 {scope} 범위에 "
        "적용한 편집본입니다."
    )

    if original_summary:
        return f"{original_summary} {suffix}"

    return suffix


def _resolve_key_points(
    *,
    chapter_plan: dict[str, Any],
    chapter_draft: dict[str, Any],
) -> list[str]:
    for value in (
        chapter_draft.get("key_points"),
        chapter_plan.get("key_points"),
    ):
        if not isinstance(value, list):
            continue

        normalized = _normalize_string_list(
            value
        )

        if normalized:
            return normalized

    return []


def _get_source_ids(
    artifact: Any,
) -> list[str]:
    if not isinstance(artifact, dict):
        return []

    value = artifact.get("source_ids")

    if not isinstance(value, list):
        return []

    return _normalize_string_list(value)


def _merge_string_lists(
    *values: Any,
) -> list[str]:
    result: list[str] = []

    for value in values:
        if not isinstance(value, list):
            continue

        for item in value:
            text = str(item).strip()

            if text and text not in result:
                result.append(text)

    return result


def _normalize_string_list(
    values: list[Any],
) -> list[str]:
    result: list[str] = []

    for item in values:
        text = str(item).strip()

        if text and text not in result:
            result.append(text)

    return result
