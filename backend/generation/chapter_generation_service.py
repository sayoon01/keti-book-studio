from __future__ import annotations

from typing import Any

from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.infrastructure.llm.ollama_json_client import (
    OllamaJsonClient,
)
from backend.generation.validators.artifact_payloads import (
    ArtifactPayloadValidationError,
    validate_chapter_draft,
    validate_editorial_decision,
    validate_final_chapter,
    validate_reader_report,
    validate_revised_chapter,
    validate_review_report,
)
from backend.generation.prompts import (
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


class ChapterGenerationService:
    def __init__(
        self,
        *,
        client: OllamaJsonClient | None = None,
        model_router: ModelRouter | None = None,
    ) -> None:
        self.client = (
            client
            or OllamaJsonClient()
        )

        self.model_router = (
            model_router
            or ModelRouter()
        )

    @staticmethod
    def _build_retry_suffix(
        attempt: int,
        previous_error: Exception | None,
    ) -> str:
        if attempt == 1:
            return ""

        return f"""

[이전 생성 실패 보완 지시]
이전 응답은 다음 이유로 폐기되었습니다:
{previous_error}

반드시 다음 조건을 지키세요.
- markdown 본문은 최소 1,500자 이상 작성
- 문장을 중간에 끊지 않기
- 같은 단어나 문장을 반복하지 않기
- 완전한 JSON 객체 하나만 반환
- markdown 문자열을 끝까지 닫기
"""

    async def write_chapter(
        self,
        *,
        plan: dict[str, Any],
        research: dict[str, Any],
        target_reader: str | None = None,
        writing_style: str | None = None,
    ) -> dict[str, Any]:
        writer_config = self.model_router.get_config(
            GenerationRole.WRITER
        )

        max_attempts = 2
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            user_prompt = build_writer_user_prompt(
                plan=plan,
                research=research,
                target_reader=target_reader,
                writing_style=writing_style,
            ) + self._build_retry_suffix(
                attempt,
                last_error,
            )

            payload = await self.client.generate_json(
                system_prompt=WRITER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=writer_config.model,
                temperature=writer_config.temperature,
            )

            try:
                return validate_chapter_draft(payload)
            except ArtifactPayloadValidationError as exc:
                last_error = exc

                if attempt >= max_attempts:
                    raise

        raise RuntimeError(
            "도달할 수 없는 코드입니다."
        )

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

# 기존 코드 호환을 위한 임시 별칭입니다.
# 새 코드는 ChapterGenerationService를 사용하세요.
ChapterLlmService = ChapterGenerationService

