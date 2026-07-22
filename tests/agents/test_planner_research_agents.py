from __future__ import annotations

from backend.orchestration.stages.planner_stage import PlannerAgent
from backend.orchestration.stages.researcher_stage import ResearchAgent
from backend.orchestration.stages.writer_stage import WriterAgent
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)


def test_planner_agent_declaration():
    agent = PlannerAgent()

    assert agent.name == "chapter_planner"
    assert agent.role == AgentRole.PLANNER.value
    assert agent.supported_stage_types == {
        ProductionStageType.CHAPTER_PLANNING.value,
    }
    assert agent.required_artifact_types == set()
    assert agent.output_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
    }


def test_research_agent_declaration():
    agent = ResearchAgent()

    assert agent.name == "chapter_researcher"
    assert agent.role == AgentRole.RESEARCHER.value
    assert agent.supported_stage_types == {
        ProductionStageType.CHAPTER_RESEARCH.value,
    }
    assert agent.required_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
    }
    assert agent.output_artifact_types == {
        ProductionArtifactType.RESEARCH_REPORT.value,
    }


def test_writer_agent_declaration():
    agent = WriterAgent()

    assert agent.name == "chapter_writer"
    assert agent.role == AgentRole.WRITER.value
    assert agent.supported_stage_types == {
        ProductionStageType.CHAPTER_WRITING.value,
    }
    assert agent.required_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
        ProductionArtifactType.RESEARCH_REPORT.value,
    }
    assert agent.output_artifact_types == {
        ProductionArtifactType.CHAPTER_DRAFT.value,
    }
