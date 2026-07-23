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


class FinalizerAgent(BasePublishingAgent):
    def __init__(
        self,
        llm_service: ChapterGenerationService | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.FINALIZER.value,
            name="chapter_finalizer",
            supported_stage_types={
                ProductionStageType.CHAPTER_FINALIZATION.value,
            },
            required_artifact_types={
                ProductionArtifactType.REVISED_CHAPTER.value,
                ProductionArtifactType.READER_REPORT.value,
            },
            output_artifact_types={
                ProductionArtifactType.FINAL_CHAPTER.value,
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
        reader_artifact = context.require_artifact(
            ProductionArtifactType.READER_REPORT
        )

        payload = await self.llm_service.finalize_chapter(
            revised=parse_artifact_content(revised_artifact),
            reader_report=parse_artifact_content(reader_artifact),
        )

        payload["based_on_revised"] = (
            revised_artifact.artifact_id
        )
        payload["based_on_reader"] = reader_artifact.artifact_id

        final_quality = payload.get("final_quality", {})

        return AgentResult.success(
            summary="최종 챕터를 확정했습니다.",
            artifacts=[
                AgentArtifact(
                    artifact_type=(
                        ProductionArtifactType
                        .FINAL_CHAPTER
                        .value
                    ),
                    name=f"{payload['title']} 최종본",
                    content=payload,
                    metadata={
                        "generated_by": self.name,
                    },
                )
            ],
            output_data={
                "publishable": payload.get("publishable"),
                "quality_score": final_quality.get("score"),
            },
        )
