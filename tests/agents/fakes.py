from __future__ import annotations

from backend.agents.base import (
    BasePublishingAgent,
)
from backend.agents.context import (
    AgentContext,
)
from backend.agents.schemas import (
    AgentArtifact,
    AgentResult,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


class FakePlannerAgent(
    BasePublishingAgent
):
    def __init__(self):
        super().__init__(
            role=AgentRole.PLANNER.value,
            name="fake_planner",
            supported_stage_types={
                ProductionStageType
                .CHAPTER_PLANNING
                .value,
            },
            output_artifact_types={
                ProductionArtifactType
                .CHAPTER_PLAN
                .value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        unit_title = (
            context.unit.title
            if context.unit
            else "Untitled"
        )

        return AgentResult.success(
            summary="챕터 계획을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .CHAPTER_PLAN
                        .value
                    ),
                    name=(
                        f"{unit_title} 챕터 계획"
                    ),
                    content={
                        "title": unit_title,
                        "sections": [
                            {
                                "title": "개요",
                                "purpose": (
                                    "핵심 개념 설명"
                                ),
                            },
                            {
                                "title": "상세 설명",
                                "purpose": (
                                    "세부 내용 설명"
                                ),
                            },
                        ],
                    },
                    metadata={
                        "generated_by": (
                            "fake_planner"
                        ),
                    },
                )
            ],
            output_data={
                "section_count": 2,
            },
        )


class FakeWriterAgent(
    BasePublishingAgent
):
    def __init__(self):
        super().__init__(
            role=AgentRole.WRITER.value,
            name="fake_writer",
            supported_stage_types={
                ProductionStageType
                .CHAPTER_WRITING
                .value,
            },
            required_artifact_types={
                ProductionArtifactType
                .CHAPTER_PLAN
                .value,
            },
            output_artifact_types={
                ProductionArtifactType
                .CHAPTER_DRAFT
                .value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        plan = context.get_latest_artifact(
            ProductionArtifactType
            .CHAPTER_PLAN
            .value
        )

        return AgentResult.success(
            summary="챕터 초안을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .CHAPTER_DRAFT
                        .value
                    ),
                    name="챕터 초안",
                    content={
                        "markdown": (
                            "# 챕터 초안\n\n"
                            f"계획: {plan.content}"
                        )
                    },
                )
            ],
        )
