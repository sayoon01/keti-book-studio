from __future__ import annotations

from typing import Any

from backend.llm import OllamaJsonClient
from backend.orchestration.artifact_payloads import (
    validate_chapter_draft,
    validate_editorial_decision,
    validate_final_chapter,
    validate_reader_report,
    validate_revised_chapter,
    validate_review_report,
)
from backend.orchestration.prompts import (
    EDITOR_SYSTEM_PROMPT,
    FINALIZER_SYSTEM_PROMPT,
    READER_SYSTEM_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
    REVISER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    build_editor_user_prompt,
    build_finalizer_user_prompt,
    build_reader_user_prompt,
    build_reviewer_user_prompt,
    build_reviser_user_prompt,
    build_writer_user_prompt,
)


class ChapterLlmService:
    def __init__(
        self,
        client: OllamaJsonClient | None = None,
    ) -> None:
        self.client = client or OllamaJsonClient()

    async def write_chapter(
        self,
        *,
        plan: dict[str, Any],
        research: dict[str, Any],
        target_reader: str | None = None,
        writing_style: str | None = None,
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=WRITER_SYSTEM_PROMPT,
            user_prompt=build_writer_user_prompt(
                plan=plan,
                research=research,
                target_reader=target_reader,
                writing_style=writing_style,
            ),
            temperature=0.5,
        )

        return validate_chapter_draft(payload)

    async def review_chapter(
        self,
        *,
        plan: dict[str, Any],
        research: dict[str, Any],
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            user_prompt=build_reviewer_user_prompt(
                plan=plan,
                research=research,
                draft=draft,
            ),
            temperature=0.1,
        )

        return validate_review_report(payload)

    async def create_editorial_decision(
        self,
        *,
        draft: dict[str, Any],
        review: dict[str, Any],
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=EDITOR_SYSTEM_PROMPT,
            user_prompt=build_editor_user_prompt(
                draft=draft,
                review=review,
            ),
            temperature=0.2,
        )

        return validate_editorial_decision(payload)

    async def revise_chapter(
        self,
        *,
        draft: dict[str, Any],
        review: dict[str, Any],
        editorial: dict[str, Any],
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=REVISER_SYSTEM_PROMPT,
            user_prompt=build_reviser_user_prompt(
                draft=draft,
                review=review,
                editorial=editorial,
            ),
            temperature=0.4,
        )

        return validate_revised_chapter(payload)

    async def test_with_reader(
        self,
        *,
        revised: dict[str, Any],
        target_reader: str | None = None,
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=READER_SYSTEM_PROMPT,
            user_prompt=build_reader_user_prompt(
                revised=revised,
                target_reader=target_reader,
            ),
            temperature=0.2,
        )

        return validate_reader_report(payload)

    async def finalize_chapter(
        self,
        *,
        revised: dict[str, Any],
        reader_report: dict[str, Any],
    ) -> dict[str, Any]:
        payload = await self.client.generate_json(
            system_prompt=FINALIZER_SYSTEM_PROMPT,
            user_prompt=build_finalizer_user_prompt(
                revised=revised,
                reader_report=reader_report,
            ),
            temperature=0.3,
        )

        return validate_final_chapter(payload)
