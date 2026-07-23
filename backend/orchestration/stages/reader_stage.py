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


class ReaderAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.READER.value,
            name="chapter_reader",
            supported_stage_types={
                ProductionStageType.CHAPTER_READER_TEST.value,
            },
            required_artifact_types={
                ProductionArtifactType.REVISED_CHAPTER.value,
            },
            output_artifact_types={
                ProductionArtifactType.READER_REPORT.value,
            },
        )
        self.llm_service = llm_service or ChapterGenerationService()

    async def _run(
        self,
        context: AgentContext,
    ) -> AgentResult:
        revised_artifact = context.require_artifact(
            ProductionArtifactType.REVISED_CHAPTER
        )

        payload = await self.llm_service.test_with_reader(
            revised=parse_artifact_content(revised_artifact),
            target_reader=None,
        )

        payload["based_on_revised"] = (
            revised_artifact.artifact_id
        )

        return AgentResult.success(
            summary="예상 독자 관점 평가를 완료했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .READER_REPORT
                        .value
                    ),
                    name=f"{payload['title']} 독자 평가",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "satisfaction": payload.get("satisfaction"),
            },
        )
