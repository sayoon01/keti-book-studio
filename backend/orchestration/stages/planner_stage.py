from __future__ import annotations

from backend.orchestration.stages.base import BasePublishingAgent
from backend.orchestration.context import AgentContext
from backend.orchestration.agent_schemas import (
    AgentArtifact,
    AgentResult,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


class PlannerAgent(BasePublishingAgent):
    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.PLANNER.value,
            name="chapter_planner",
            supported_stage_types={
                ProductionStageType.CHAPTER_PLANNING.value,
            },
            required_artifact_types=set(),
            output_artifact_types={
                ProductionArtifactType.CHAPTER_PLAN.value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        unit_title = (
            context.unit.title
            if context.unit
            else context.book.title
        )

        return AgentResult.success(
            summary="챕터 계획을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType.CHAPTER_PLAN.value
                    ),
                    name=f"{unit_title} 챕터 계획",
                    content={
                        "title": unit_title,
                        "sections": [
                            {
                                "title": "개요",
                                "purpose": "핵심 개념 설명",
                            },
                            {
                                "title": "본문",
                                "purpose": "세부 내용 전개",
                            },
                        ],
                    },
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "section_count": 2,
            },
        )
