from __future__ import annotations

from backend.orchestration.stages import (
    AgentRegistry,
    EditorAgent,
    FinalizerAgent,
    PlannerAgent,
    ReaderAgent,
    ResearchAgent,
    ReviewerAgent,
    ReviserAgent,
    WriterAgent,
)


def build_publishing_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()

    registry.register(PlannerAgent())
    registry.register(ResearchAgent())
    registry.register(WriterAgent())
    registry.register(ReviewerAgent())
    registry.register(EditorAgent())
    registry.register(ReviserAgent())
    registry.register(ReaderAgent())
    registry.register(FinalizerAgent())

    return registry
