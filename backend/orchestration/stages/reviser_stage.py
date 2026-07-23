from __future__ import annotations

from backend.orchestration.stages.base import BasePublishingAgent
from backend.orchestration.context import AgentContext
from backend.orchestration.agent_schemas import (
    AgentArtifact,
    AgentResult,
)
from backend.orchestration.artifact_content import (
    parse_artifact_content,
)
from backend.generation.chapter_generation_service import (
    ChapterGenerationService,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


class ReviserAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.REVISER.value,
            name="chapter_reviser",
            supported_stage_types={
                ProductionStageType.CHAPTER_REVISION.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
                ProductionArtifactType.EDITORIAL_DECISION.value,
            },
            output_artifact_types={
                ProductionArtifactType.REVISED_CHAPTER.value,
            },
        )
        self.llm_service = llm_service or ChapterGenerationService()

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        draft_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_DRAFT
        )
        review_artifact = context.require_artifact(
            ProductionArtifactType.AGGREGATED_REVIEW_REPORT
        )
        editorial_artifact = context.require_artifact(
            ProductionArtifactType.EDITORIAL_DECISION
        )

        payload = await self.llm_service.revise_chapter(
            draft=parse_artifact_content(draft_artifact),
            review=parse_artifact_content(review_artifact),
            editorial=parse_artifact_content(editorial_artifact),
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_review"] = review_artifact.artifact_id
        payload["based_on_editorial"] = (
            editorial_artifact.artifact_id
        )

        applied_changes = payload.get("applied_changes", [])

        return AgentResult.success(
            summary="챕터 수정본을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .REVISED_CHAPTER
                        .value
                    ),
                    name=f"{payload['title']} 수정본",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "applied_change_count": len(applied_changes),
            },
        )
