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


class ReviewerAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.REVIEW_AGGREGATOR.value,
            name="chapter_reviewer",
            supported_stage_types={
                ProductionStageType.CHAPTER_REVIEW.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
                ProductionArtifactType.CHAPTER_PLAN.value,
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.AGGREGATED_REVIEW_REPORT.value,
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
        plan_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        research_artifact = context.require_artifact(
            ProductionArtifactType.RESEARCH_REPORT
        )

        payload = await self.llm_service.review_chapter(
            plan=parse_artifact_content(plan_artifact),
            research=parse_artifact_content(research_artifact),
            draft=parse_artifact_content(draft_artifact),
        )

        payload["based_on_draft"] = draft_artifact.artifact_id
        payload["based_on_plan"] = plan_artifact.artifact_id
        payload["based_on_research"] = (
            research_artifact.artifact_id
        )

        return AgentResult.success(
            summary="챕터 초안 품질 검토를 완료했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .AGGREGATED_REVIEW_REPORT
                        .value
                    ),
                    name=f"{payload['title']} 검토 보고서",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "passed": payload.get("passed"),
                "quality_score": payload.get("quality_score"),
            },
        )
