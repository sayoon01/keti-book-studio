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
from backend.orchestration.chapter_llm_service import (
    ChapterLlmService,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


class WriterAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterLlmService | None = None,
    ) -> None:
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
        self.llm_service = llm_service or ChapterLlmService()

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        plan_artifact = context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
        research_artifact = context.require_artifact(
            ProductionArtifactType.RESEARCH_REPORT
        )

        plan = parse_artifact_content(plan_artifact)
        research = parse_artifact_content(research_artifact)

        payload = await self.llm_service.write_chapter(
            plan=plan,
            research=research,
            target_reader=context.book.target_reader,
            writing_style=None,
        )

        payload["based_on_plan"] = plan_artifact.artifact_id
        payload["based_on_research"] = (
            research_artifact.artifact_id
        )

        return AgentResult.success(
            summary="챕터 초안을 생성했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType.CHAPTER_DRAFT.value
                    ),
                    name=f"{payload['title']} 초안",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
        )
