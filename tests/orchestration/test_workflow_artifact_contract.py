from __future__ import annotations

import pytest

from backend.orchestration.publishing_agent_registry import (
    build_publishing_agent_registry,
)
from backend.orchestration.workflow_validator import (
    WorkflowValidationError,
    validate_workflow_artifact_contract,
)
from backend.publishing.enums import (
    ProductionStageType,
)
from backend.publishing.production_schemas import (
    ProductionStageDefinition,
)
from backend.publishing.workflows import (
    build_chapter_workflow,
)


def test_chapter_workflow_satisfies_agent_artifact_contract():
    registry = build_publishing_agent_registry()

    workflow = build_chapter_workflow(
        unit_id="unit-test"
    )

    validate_workflow_artifact_contract(
        stages=workflow,
        agent_registry=registry,
    )


def test_review_dependency_missing_plan_and_research_fails():
    registry = build_publishing_agent_registry()
    unit_id = "unit-validation-test"

    broken_review = ProductionStageDefinition(
        stage_key=f"{unit_id}:review",
        stage_type=ProductionStageType.CHAPTER_REVIEW,
        order_index=40,
        unit_id=unit_id,
        depends_on=[f"{unit_id}:write"],
    )

    write = ProductionStageDefinition(
        stage_key=f"{unit_id}:write",
        stage_type=ProductionStageType.CHAPTER_WRITING,
        order_index=30,
        unit_id=unit_id,
        depends_on=[],
    )

    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow_artifact_contract(
            stages=[write, broken_review],
            agent_registry=registry,
        )

    message = str(exc_info.value)

    assert f"{unit_id}:review" in message
    assert "CHAPTER_PLAN" in message
    assert "RESEARCH_REPORT" in message
    assert "CHAPTER_DRAFT" in message
