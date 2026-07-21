from __future__ import annotations

import pytest

from backend.agents.registry import (
    AgentRegistry,
)
from backend.publishing.enums import (
    AgentRole,
    ProductionStageType,
)
from tests.agents.fakes import (
    FakePlannerAgent,
)


def test_register_and_get_agent():
    registry = AgentRegistry()

    planner = FakePlannerAgent()

    registry.register(planner)

    found = registry.get_by_role(
        AgentRole.PLANNER.value
    )

    assert found is planner

    stage_agents = registry.find_by_stage(
        ProductionStageType
        .CHAPTER_PLANNING
        .value
    )

    assert len(stage_agents) == 1
    assert stage_agents[0] is planner


def test_duplicate_role_is_rejected():
    registry = AgentRegistry()

    registry.register(
        FakePlannerAgent()
    )

    with pytest.raises(
        ValueError,
        match="이미 등록된 Agent Role",
    ):
        registry.register(
            FakePlannerAgent()
        )
