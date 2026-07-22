from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from backend.orchestration.stages.base import (
    BasePublishingAgent,
)


class AgentRegistry:
    def __init__(self):
        self._agents_by_role: dict[
            str,
            BasePublishingAgent,
        ] = {}

        self._agents_by_stage: dict[
            str,
            list[BasePublishingAgent],
        ] = defaultdict(list)

    def register(
        self,
        agent: BasePublishingAgent,
        *,
        replace: bool = False,
    ) -> None:
        existing = self._agents_by_role.get(
            agent.role
        )

        if existing and not replace:
            raise ValueError(
                f"이미 등록된 Agent Role입니다: "
                f"{agent.role}"
            )

        if existing and replace:
            self.unregister(agent.role)

        self._agents_by_role[
            agent.role
        ] = agent

        for stage_type in (
            agent.supported_stage_types
        ):
            if (
                agent
                not in self._agents_by_stage[
                    stage_type
                ]
            ):
                self._agents_by_stage[
                    stage_type
                ].append(agent)

    def register_many(
        self,
        agents: Iterable[
            BasePublishingAgent
        ],
        *,
        replace: bool = False,
    ) -> None:
        for agent in agents:
            self.register(
                agent,
                replace=replace,
            )

    def unregister(
        self,
        role: str,
    ) -> BasePublishingAgent | None:
        agent = self._agents_by_role.pop(
            role,
            None,
        )

        if not agent:
            return None

        for stage_type in (
            agent.supported_stage_types
        ):
            agents = self._agents_by_stage.get(
                stage_type,
                [],
            )

            self._agents_by_stage[
                stage_type
            ] = [
                registered
                for registered in agents
                if registered.role != role
            ]

        return agent

    def get_by_role(
        self,
        role: str,
    ) -> BasePublishingAgent:
        agent = self._agents_by_role.get(role)

        if not agent:
            raise KeyError(
                f"등록되지 않은 Agent Role입니다: "
                f"{role}"
            )

        return agent

    def find_by_stage(
        self,
        stage_type: str,
    ) -> list[BasePublishingAgent]:
        return list(
            self._agents_by_stage.get(
                stage_type,
                [],
            )
        )

    def get_single_for_stage(
        self,
        stage_type: str,
    ) -> BasePublishingAgent:
        agents = self.find_by_stage(
            stage_type
        )

        if not agents:
            raise KeyError(
                "Stage를 처리할 Agent가 없습니다: "
                f"{stage_type}"
            )

        if len(agents) > 1:
            roles = ", ".join(
                agent.role
                for agent in agents
            )

            raise ValueError(
                "Stage에 여러 Agent가 등록되어 "
                "있습니다. 역할을 명시해야 합니다: "
                f"{roles}"
            )

        return agents[0]

    def has_role(
        self,
        role: str,
    ) -> bool:
        return role in self._agents_by_role

    def list_roles(self) -> list[str]:
        return sorted(
            self._agents_by_role.keys()
        )

    def clear(self) -> None:
        self._agents_by_role.clear()
        self._agents_by_stage.clear()


_default_registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    return _default_registry
