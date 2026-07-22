from __future__ import annotations

from backend.orchestration.publishing_agent_registry import (
    build_publishing_agent_registry,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionArtifactType,
    ProductionStageType,
)
from tests.agents.fakes import (
    FakeProductionWriterAgent,
    FakeResearcherAgent,
    FakeWriterAgent,
)


def test_fake_writer_keeps_plan_only_requirement():
    agent = FakeWriterAgent()

    assert agent.required_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
    }


def test_fake_researcher_agent_declaration():
    agent = FakeResearcherAgent()

    assert agent.name == "fake_researcher"
    assert agent.role == AgentRole.RESEARCHER.value
    assert agent.required_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
    }
    assert agent.output_artifact_types == {
        ProductionArtifactType.RESEARCH_REPORT.value,
    }


def test_fake_production_writer_requires_plan_and_research():
    agent = FakeProductionWriterAgent()

    assert agent.name == "fake_production_writer"
    assert agent.required_artifact_types == {
        ProductionArtifactType.CHAPTER_PLAN.value,
        ProductionArtifactType.RESEARCH_REPORT.value,
    }
    assert agent.output_artifact_types == {
        ProductionArtifactType.CHAPTER_DRAFT.value,
    }


def test_build_publishing_agent_registry():
    registry = build_publishing_agent_registry()

    assert registry.get_by_role(
        AgentRole.PLANNER.value
    ).name == "chapter_planner"

    assert registry.get_by_role(
        AgentRole.RESEARCHER.value
    ).name == "chapter_researcher"

    assert registry.get_by_role(
        AgentRole.WRITER.value
    ).name == "chapter_writer"

    assert registry.get_single_for_stage(
        ProductionStageType.CHAPTER_PLANNING.value
    ).name == "chapter_planner"

    assert registry.get_single_for_stage(
        ProductionStageType.CHAPTER_RESEARCH.value
    ).name == "chapter_researcher"

    assert registry.get_single_for_stage(
        ProductionStageType.CHAPTER_WRITING.value
    ).name == "chapter_writer"
