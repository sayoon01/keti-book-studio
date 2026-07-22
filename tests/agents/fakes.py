from __future__ import annotations

from backend.orchestration.stages.base import (
    BasePublishingAgent,
)
from backend.orchestration.context import (
    AgentContext,
)
from backend.orchestration.agent_schemas import (
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


class FakeResearcherAgent(
    BasePublishingAgent
):
    def __init__(self):
        super().__init__(
            role=AgentRole.RESEARCHER.value,
            name="fake_researcher",
            supported_stage_types={
                ProductionStageType
                .CHAPTER_RESEARCH
                .value,
            },
            required_artifact_types={
                ProductionArtifactType
                .CHAPTER_PLAN
                .value,
            },
            output_artifact_types={
                ProductionArtifactType
                .RESEARCH_REPORT
                .value,
            },
        )

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        return AgentResult.success(
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .RESEARCH_REPORT
                        .value
                    ),
                    name="Fake research report",
                    content={
                        "summary": "테스트 조사 결과",
                    },
                )
            ],
            summary="Fake Researcher 실행 완료",
        )


class FakeProductionWriterAgent(
    BasePublishingAgent
):
    def __init__(self):
        super().__init__(
            role=AgentRole.WRITER.value,
            name="fake_production_writer",
            supported_stage_types={
                ProductionStageType
                .CHAPTER_WRITING
                .value,
            },
            required_artifact_types={
                ProductionArtifactType
                .CHAPTER_PLAN
                .value,
                ProductionArtifactType
                .RESEARCH_REPORT
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

        research = context.get_latest_artifact(
            ProductionArtifactType
            .RESEARCH_REPORT
            .value
        )

        return AgentResult.success(
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .CHAPTER_DRAFT
                        .value
                    ),
                    name="Fake chapter draft",
                    content={
                        "plan_id": (
                            plan.artifact_id
                            if plan
                            else None
                        ),
                        "research_id": (
                            research.artifact_id
                            if research
                            else None
                        ),
                        "markdown": "# 테스트 초안",
                    },
                )
            ],
            summary="Fake Writer 실행 완료",
        )
