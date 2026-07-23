from __future__ import annotations

from typing import Any

from backend.generation.handlers.structured_json_handler import (
    StructuredJsonHandler,
    metadata_to_dict,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_researcher import (
    build_chapter_researcher_prompts,
)
from backend.generation.validators import (
    validate_research_artifact,
)
from backend.infrastructure.llm import OllamaClient


class ResearchHandler:
    """
    Researcher 역할 전용 Generation Handler.
    """

    def __init__(
        self,
        *,
        client: OllamaClient,
        model_router: ModelRouter,
        max_attempts: int,
    ) -> None:
        self._generator = StructuredJsonHandler(
            role=GenerationRole.RESEARCHER,
            client=client,
            model_router=model_router,
            max_attempts=max_attempts,
        )

    async def run(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        sources: list[dict[str, Any]],
        previous_chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompts = build_chapter_researcher_prompts(
            book_config=book_config,
            chapter_plan=chapter_plan,
            sources=sources,
            previous_chapters=previous_chapters,
        )

        chapter_id = _get_chapter_id(
            chapter_plan
        )

        chapter_title = str(
            chapter_plan.get("title", "")
        ).strip()

        def enrich_payload(
            payload: dict[str, Any],
            metadata: Any,
            attempt: int,
        ) -> dict[str, Any]:
            result = dict(payload)

            # LLM이 다른 chapter_id를 출력해도
            # 파이프라인 입력값을 정본으로 사용한다.
            result["chapter_id"] = chapter_id

            if not str(
                result.get("title", "")
            ).strip():
                result["title"] = chapter_title

            result["metadata"] = {
                **metadata_to_dict(metadata),
                "role": GenerationRole.RESEARCHER.value,
                "response_format": "json",
                "attempt": attempt,
            }

            return result

        return await self._generator.generate(
            system_prompt=prompts.system_prompt,
            user_prompt=prompts.user_prompt,
            validator=validate_research_artifact,
            enrich_payload=enrich_payload,
            operation_name="Chapter Researcher",
        )


def _get_chapter_id(
    chapter_plan: dict[str, Any],
) -> str:
    value = (
        chapter_plan.get("chapter_id")
        or chapter_plan.get("unit_id")
        or chapter_plan.get("id")
        or ""
    )

    normalized = str(value).strip()

    if not normalized:
        raise ValueError(
            "chapter_plan에 chapter_id가 필요합니다."
        )

    return normalized
