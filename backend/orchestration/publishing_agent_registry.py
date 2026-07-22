from __future__ import annotations

from backend.agents.editor import EditorAgent
from backend.agents.finalizer import FinalizerAgent
from backend.agents.planner import PlannerAgent
from backend.agents.reader import ReaderAgent
from backend.agents.registry import AgentRegistry
from backend.agents.researcher import ResearchAgent
from backend.agents.reviewer import ReviewerAgent
from backend.agents.reviser import ReviserAgent
from backend.agents.writer import WriterAgent


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
