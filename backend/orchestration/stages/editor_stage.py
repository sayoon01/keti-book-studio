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


class EditorAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.EDITOR.value,
            name="chapter_editor",
            supported_stage_types={
                ProductionStageType.CHAPTER_EDITING.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.EDITORIAL_DECISION.value,
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

        payload = await self.llm_service.create_editorial_decision(
            draft=parse_artifact_content(draft_artifact),
            review=parse_artifact_content(review_artifact),
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_review"] = review_artifact.artifact_id

        return AgentResult.success(
            summary="편집 지시서를 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .EDITORIAL_DECISION
                        .value
                    ),
                    name=f"{payload['title']} 편집 지시서",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
        )
