from __future__ import annotations

from backend.agents.planner import PlannerAgent
from backend.agents.registry import AgentRegistry
from backend.agents.researcher import ResearchAgent
from backend.agents.writer import WriterAgent


def build_publishing_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()

    registry.register(PlannerAgent())
    registry.register(ResearchAgent())
    registry.register(WriterAgent())

    return registry
