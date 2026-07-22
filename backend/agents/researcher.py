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


class ResearchAgent(BasePublishingAgent):
    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.RESEARCHER.value,
            name="chapter_researcher",
            supported_stage_types={
                ProductionStageType.CHAPTER_RESEARCH.value,
            },
            required_artifact_types={
                ProductionArtifactType.CHAPTER_PLAN.value,
            },
            output_artifact_types={
                ProductionArtifactType.RESEARCH_REPORT.value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        plan = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )

        unit_title = (
            context.unit.title
            if context.unit
            else plan.content.get("title", "Untitled")
        )

        source_titles = [
            source.title for source in context.sources
        ]

        return AgentResult.success(
            summary="챕터 조사 보고서를 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType.RESEARCH_REPORT.value
                    ),
                    name=f"{unit_title} 조사 보고서",
                    content={
                        "title": unit_title,
                        "based_on_plan": plan.artifact_id,
                        "key_points": [
                            "핵심 주장 정리",
                            "근거 활용 방향",
                            "주의사항",
                        ],
                        "source_titles": source_titles,
                        "plan_sections": plan.content.get(
                            "sections",
                            [],
                        ),
                    },
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "source_count": len(source_titles),
            },
        )
