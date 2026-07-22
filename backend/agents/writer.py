from __future__ import annotations

from backend.agents.base import BasePublishingAgent
from backend.agents.context import AgentContext
from backend.agents.schemas import (
    AgentArtifact,
    AgentResult,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


class WriterAgent(BasePublishingAgent):
    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.WRITER.value,
            name="chapter_writer",
            supported_stage_types={
                ProductionStageType.CHAPTER_WRITING.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_PLAN.value,
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.CHAPTER_DRAFT.value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        plan = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        research = context.require_artifact(
            ProductionArtifactType.RESEARCH_REPORT
        )

        unit_title = (
            context.unit.title
            if context.unit
            else plan.content.get("title", "Untitled")
        )

        return AgentResult.success(
            summary="챕터 초안을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType.CHAPTER_DRAFT.value
                    ),
                    name=f"{unit_title} 초안",
                    content={
                        "title": unit_title,
                        "markdown": (
                            f"# {unit_title}\n\n"
                            f"계획: {plan.content}\n\n"
                            f"조사: {research.content}\n"
                        ),
                        "based_on_plan": plan.artifact_id,
                        "based_on_research": (
                            research.artifact_id
                        ),
                    },
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
        )
