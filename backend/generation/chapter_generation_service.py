from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict
from typing import Any

from backend.generation.handlers import (
    ResearchHandler,
    ReviewerHandler,
    ReviserHandler,
    StructuredGenerationError,
    TextGenerationError,
)
from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)
from backend.generation.prompts.chapter_writer import (
    build_chapter_writer_prompts,
)
from backend.generation.validators.artifact_payloads import (
    ArtifactPayloadValidationError,
    ArtifactValidationError,
    validate_chapter_draft,
)
from backend.infrastructure.llm import (
    OllamaClient,
    OllamaClientError,
)


logger = logging.getLogger(__name__)


class ChapterGenerationError(RuntimeError):
    """
    챕터 Generation Service 처리 실패.
    """


class ChapterGenerationService:
    """
    챕터 생성 단계의 단일 진입점.

    책임:
    - 역할별 Handler 위임
    - Writer Markdown 생성 (현 단계 유지)

    하지 않는 일:
    - Stage 실행 순서 결정
    - DB 직접 저장
    - 이벤트 발행
    - ADK Agent 라우팅
    """

    def __init__(
        self,
        *,
        client: OllamaClient | None = None,
        model_router: ModelRouter | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self._client = client or OllamaClient()
        self._model_router = model_router or ModelRouter()

        self._max_attempts = (
            max_attempts
            if max_attempts is not None
            else _read_positive_int_env(
                "BOOK_STUDIO_GENERATION_MAX_ATTEMPTS",
                2,
            )
        )

        # Writer 루프 호환
        self._generation_max_attempts = self._max_attempts

        self._writer_num_ctx = _read_positive_int_env(
            "BOOK_STUDIO_WRITER_NUM_CTX",
            8192,
        )

        self._research_handler = ResearchHandler(
            client=self._client,
            model_router=self._model_router,
            max_attempts=self._max_attempts,
        )

        self._reviewer_handler = ReviewerHandler(
            client=self._client,
            model_router=self._model_router,
            max_attempts=self._max_attempts,
        )

        self._reviser_handler = ReviserHandler(
            client=self._client,
            model_router=self._model_router,
            max_attempts=self._max_attempts,
        )

    async def research_chapter(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        sources: list[dict[str, Any]] | None = None,
        previous_chapters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        ResearchHandler에 Research Artifact 생성을 위임한다.
        """

        try:
            return await self._research_handler.run(
                book_config=book_config,
                chapter_plan=chapter_plan,
                sources=sources or [],
                previous_chapters=previous_chapters or [],
            )

        except StructuredGenerationError as exc:
            raise ChapterGenerationError(
                "Research Artifact 생성에 실패했습니다."
            ) from exc

    async def write_chapter(
        self,
        *,
        chapter_plan: dict[str, Any],
        research: dict[str, Any],
        book_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        하나의 챕터 초안을 Markdown으로 생성한다.
        """

        self._validate_inputs(
            chapter_plan=chapter_plan,
            research=research,
            book_context=book_context,
        )

        writer_config = self._model_router.get_config(
            GenerationRole.WRITER
        )

        last_error: Exception | None = None

        for generation_attempt in range(
            1,
            self._generation_max_attempts + 1,
        ):
            retry_reason = (
                str(last_error)
                if last_error is not None
                else None
            )

            prompts = build_chapter_writer_prompts(
                chapter_plan=chapter_plan,
                research=research,
                book_context=book_context,
                retry_reason=retry_reason,
            )

            logger.info(
                "Chapter Writer started: "
                "attempt=%s/%s model=%s "
                "num_predict=%s num_ctx=%s",
                generation_attempt,
                self._generation_max_attempts,
                writer_config.model,
                writer_config.num_predict,
                self._writer_num_ctx,
            )

            try:
                result = await self._client.generate_text(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                    model=writer_config.model,
                    temperature=writer_config.temperature,
                    timeout_seconds=(
                        writer_config.timeout_seconds
                    ),
                    num_predict=writer_config.num_predict,
                    num_ctx=self._writer_num_ctx,
                    minimum_length=300,
                )

                payload = self._build_chapter_payload(
                    markdown=result.text,
                    chapter_plan=chapter_plan,
                    research=research,
                )

                validated_payload = validate_chapter_draft(
                    payload,
                    minimum_markdown_length=300,
                )

            except (
                ArtifactValidationError,
                ArtifactPayloadValidationError,
                OllamaClientError,
                ValueError,
                TypeError,
            ) as exc:
                last_error = exc

                logger.warning(
                    "Chapter Writer failed: "
                    "attempt=%s/%s model=%s error=%s",
                    generation_attempt,
                    self._generation_max_attempts,
                    writer_config.model,
                    exc,
                )

                if (
                    generation_attempt
                    >= self._generation_max_attempts
                ):
                    raise ChapterGenerationError(
                        "Chapter Draft 생성에 실패했습니다. "
                        f"model={writer_config.model}, "
                        f"attempts="
                        f"{self._generation_max_attempts}, "
                        f"last_error={last_error}"
                    ) from last_error

                await asyncio.sleep(1)
                continue

            generation_metadata = {
                **asdict(result.metadata),
                "role": GenerationRole.WRITER.value,
                "response_format": "markdown",
                "temperature": writer_config.temperature,
                "timeout_seconds": (
                    writer_config.timeout_seconds
                ),
                "num_predict": writer_config.num_predict,
                "num_ctx": self._writer_num_ctx,
                "generation_attempt": generation_attempt,
            }

            logger.info(
                "Chapter Writer completed: "
                "model=%s markdown_length=%s "
                "latency_seconds=%s",
                writer_config.model,
                len(validated_payload["markdown"]),
                generation_metadata["latency_seconds"],
            )

            return {
                **validated_payload,
                "_generation": generation_metadata,
            }

        raise ChapterGenerationError(
            "Chapter Draft 생성에 실패했습니다. "
            f"attempts={self._generation_max_attempts}, "
            f"last_error={last_error}"
        )

    async def review_chapter(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        research_artifact: dict[str, Any] | None = None,
        chapter_draft: dict[str, Any] | None = None,
        research: dict[str, Any] | None = None,
        draft: dict[str, Any] | None = None,
        previous_chapters: list[dict[str, Any]] | None = None,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Chapter Draft를 검토하여 REVIEW_ARTIFACT를 생성한다.

        정본 인자:
        - research_artifact
        - chapter_draft

        임시 호환 인자:
        - research
        - draft
        - plan
        """

        resolved_plan = (
            chapter_plan
            if chapter_plan
            else (plan or {})
        )

        resolved_research = (
            research_artifact
            if research_artifact is not None
            else research
        )

        resolved_draft = (
            chapter_draft
            if chapter_draft is not None
            else draft
        )

        if not isinstance(resolved_research, dict):
            raise ChapterGenerationError(
                "review_chapter에는 research_artifact가 필요합니다."
            )

        if not isinstance(resolved_draft, dict):
            raise ChapterGenerationError(
                "review_chapter에는 chapter_draft가 필요합니다."
            )

        try:
            return await self._reviewer_handler.run(
                book_config=book_config,
                chapter_plan=resolved_plan,
                research_artifact=resolved_research,
                chapter_draft=resolved_draft,
                previous_chapters=previous_chapters or [],
            )

        except StructuredGenerationError as exc:
            raise ChapterGenerationError(
                "Review Artifact 생성에 실패했습니다."
            ) from exc

    async def revise_chapter(
        self,
        *,
        book_config: dict[str, Any],
        chapter_plan: dict[str, Any],
        research_artifact: dict[str, Any] | None = None,
        chapter_draft: dict[str, Any] | None = None,
        review_artifact: dict[str, Any] | None = None,
        research: dict[str, Any] | None = None,
        draft: dict[str, Any] | None = None,
        review: dict[str, Any] | None = None,
        previous_chapters: list[dict[str, Any]] | None = None,
        revision_number: int = 1,
    ) -> dict[str, Any]:
        """
        Reviewer의 수정 지침을 반영하여
        새로운 CHAPTER_DRAFT를 생성한다.

        정본 인자:
        - research_artifact
        - chapter_draft
        - review_artifact

        임시 하위 호환 인자:
        - research
        - draft
        - review
        """

        resolved_research = (
            research_artifact
            if research_artifact is not None
            else research
        )

        resolved_draft = (
            chapter_draft
            if chapter_draft is not None
            else draft
        )

        resolved_review = (
            review_artifact
            if review_artifact is not None
            else review
        )

        if not isinstance(resolved_research, dict):
            raise ChapterGenerationError(
                "revise_chapter에는 "
                "research_artifact가 필요합니다."
            )

        if not isinstance(resolved_draft, dict):
            raise ChapterGenerationError(
                "revise_chapter에는 "
                "chapter_draft가 필요합니다."
            )

        if not isinstance(resolved_review, dict):
            raise ChapterGenerationError(
                "revise_chapter에는 "
                "review_artifact가 필요합니다."
            )

        if (
            not isinstance(revision_number, int)
            or isinstance(revision_number, bool)
            or revision_number <= 0
        ):
            raise ChapterGenerationError(
                "revision_number는 1 이상의 정수여야 합니다."
            )

        try:
            return await self._reviser_handler.run(
                book_config=book_config,
                chapter_plan=chapter_plan,
                research_artifact=resolved_research,
                chapter_draft=resolved_draft,
                review_artifact=resolved_review,
                previous_chapters=previous_chapters or [],
                revision_number=revision_number,
            )

        except TextGenerationError as exc:
            raise ChapterGenerationError(
                "Revised Chapter Draft 생성에 실패했습니다."
            ) from exc

    @staticmethod
    def _validate_inputs(
        *,
        chapter_plan: dict[str, Any],
        research: dict[str, Any],
        book_context: dict[str, Any] | None,
    ) -> None:
        if not isinstance(chapter_plan, dict):
            raise TypeError(
                "chapter_plan은 dict여야 합니다."
            )

        if not isinstance(research, dict):
            raise TypeError(
                "research는 dict여야 합니다."
            )

        if (
            book_context is not None
            and not isinstance(book_context, dict)
        ):
            raise TypeError(
                "book_context는 dict 또는 None이어야 합니다."
            )

        title = chapter_plan.get("title")

        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                "chapter_plan.title이 비어 있습니다."
            )

    @staticmethod
    def _build_chapter_payload(
        *,
        markdown: str,
        chapter_plan: dict[str, Any],
        research: dict[str, Any],
    ) -> dict[str, Any]:
        """
        LLM이 생성한 Markdown과 이미 존재하는 구조 정보를 합친다.

        title, summary, key_points, source_ids를 LLM이 다시 만들게
        하지 않고 기존 계획 및 조사 결과를 사용한다.
        """

        title = _resolve_title(
            chapter_plan=chapter_plan,
            markdown=markdown,
        )

        summary = _resolve_summary(
            title=title,
            chapter_plan=chapter_plan,
            research=research,
        )

        key_points = _resolve_key_points(
            title=title,
            chapter_plan=chapter_plan,
            research=research,
        )

        source_ids = _resolve_source_ids(
            chapter_plan=chapter_plan,
            research=research,
        )

        chapter_id = str(
            chapter_plan.get("chapter_id")
            or chapter_plan.get("unit_id")
            or chapter_plan.get("id")
            or ""
        )

        return {
            "chapter_id": chapter_id,
            "title": title,
            "summary": summary,
            "markdown": markdown.strip(),
            "key_points": key_points,
            "source_ids": source_ids,
        }


# 이전 코드에서 ChapterLlmService를 import하고 있을 가능성을 위해
# 3단계 전까지 임시 호환 Alias를 유지한다.
ChapterLlmService = ChapterGenerationService


# ============================================================
# Payload helpers
# ============================================================


def _resolve_title(
    *,
    chapter_plan: dict[str, Any],
    markdown: str,
) -> str:
    planned_title = chapter_plan.get("title")

    if (
        isinstance(planned_title, str)
        and planned_title.strip()
    ):
        return planned_title.strip()

    for line in markdown.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            generated_title = stripped[2:].strip()

            if generated_title:
                return generated_title

    return "제목 없는 챕터"


def _resolve_summary(
    *,
    title: str,
    chapter_plan: dict[str, Any],
    research: dict[str, Any],
) -> str:
    candidates = (
        chapter_plan.get("description"),
        research.get("research_summary"),
        research.get("summary"),
    )

    for candidate in candidates:
        if (
            isinstance(candidate, str)
            and candidate.strip()
        ):
            return candidate.strip()

    return f"{title}의 주요 개념과 적용 방법을 설명한다."


def _resolve_key_points(
    *,
    title: str,
    chapter_plan: dict[str, Any],
    research: dict[str, Any],
) -> list[str]:
    key_points: list[str] = []

    candidate_lists = (
        chapter_plan.get("required_points"),
        chapter_plan.get("objectives"),
        chapter_plan.get("key_points"),
        research.get("key_points"),
    )

    for candidate_list in candidate_lists:
        if not isinstance(candidate_list, list):
            continue

        for item in candidate_list:
            if not isinstance(item, str):
                continue

            normalized = item.strip()

            if (
                normalized
                and normalized not in key_points
            ):
                key_points.append(normalized)

    findings = research.get("findings", [])

    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue

            topic = str(
                finding.get("topic", "")
            ).strip()

            if topic and topic not in key_points:
                key_points.append(topic)

    fallback_points = [
        f"{title}의 기본 개념",
        f"{title}의 주요 구성요소",
        f"{title}의 실제 적용 시 고려사항",
    ]

    for fallback in fallback_points:
        if len(key_points) >= 3:
            break

        if fallback not in key_points:
            key_points.append(fallback)

    return key_points


def _resolve_source_ids(
    *,
    chapter_plan: dict[str, Any],
    research: dict[str, Any],
) -> list[str]:
    candidate_lists = (
        research.get("source_ids"),
        chapter_plan.get("source_ids"),
    )

    source_ids: list[str] = []

    for candidate_list in candidate_lists:
        if not isinstance(candidate_list, list):
            continue

        for item in candidate_list:
            if not isinstance(item, str):
                continue

            normalized = item.strip()

            if (
                normalized
                and normalized not in source_ids
            ):
                source_ids.append(normalized)

    return source_ids


def _read_positive_int_env(
    name: str,
    fallback: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return fallback

    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name}은 정수여야 합니다. "
            f"actual={raw_value!r}"
        ) from exc

    if parsed <= 0:
        raise ValueError(
            f"{name}은 0보다 커야 합니다. "
            f"actual={parsed}"
        )

    return parsed


# 구 이름 호환
_read_int_env = _read_positive_int_env
