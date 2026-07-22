from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from backend.agents.registry import AgentRegistry
from backend.publishing.production_schemas import (
    ProductionStageDefinition,
)


class WorkflowValidationError(ValueError):
    """워크플로와 Agent Artifact 계약이 맞지 않을 때 발생합니다."""


def _stage_type_value(stage_type: str | Enum) -> str:
    if isinstance(stage_type, Enum):
        return str(stage_type.value)

    return str(stage_type)


def validate_workflow_artifact_contract(
    *,
    stages: Iterable[ProductionStageDefinition],
    agent_registry: AgentRegistry,
) -> None:
    """
    각 Stage Agent가 요구하는 Artifact가 dependency Stage들의
    output_artifact_types 합집합으로 충족되는지 검사합니다.
    """

    stage_list = list(stages)

    stages_by_key = {
        stage.stage_key: stage
        for stage in stage_list
    }

    output_types_by_stage_key: dict[str, set[str]] = {}

    for stage in stage_list:
        agent = agent_registry.get_single_for_stage(
            _stage_type_value(stage.stage_type)
        )

        output_types_by_stage_key[stage.stage_key] = set(
            agent.output_artifact_types
        )

    errors: list[str] = []

    for stage in stage_list:
        agent = agent_registry.get_single_for_stage(
            _stage_type_value(stage.stage_type)
        )

        required_types = set(
            agent.required_artifact_types
        )

        provided_types: set[str] = set()

        for dependency_key in stage.depends_on:
            dependency_stage = stages_by_key.get(
                dependency_key
            )

            if dependency_stage is None:
                errors.append(
                    f"{stage.stage_key}: 존재하지 않는 dependency "
                    f"{dependency_key}"
                )
                continue

            provided_types.update(
                output_types_by_stage_key.get(
                    dependency_key,
                    set(),
                )
            )

        missing_types = (
            required_types - provided_types
        )

        if missing_types:
            errors.append(
                f"{stage.stage_key}: "
                f"required={sorted(required_types)}, "
                f"provided={sorted(provided_types)}, "
                f"missing={sorted(missing_types)}, "
                f"depends_on={stage.depends_on}"
            )

    if errors:
        message = "\n".join(
            [
                "Workflow Artifact 계약 검증에 실패했습니다.",
                *[
                    f"- {error}"
                    for error in errors
                ],
            ]
        )

        raise WorkflowValidationError(message)
