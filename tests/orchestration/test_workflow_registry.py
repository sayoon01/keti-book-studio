import pytest

from backend.orchestration.workflow_registry import (
    WorkflowAlreadyRegisteredError,
    WorkflowNotFoundError,
    WorkflowRegistry,
)
from backend.publishing.enums import (
    ProductionStageType,
)


def make_test_workflow(
    *,
    name: str = "test-workflow",
    unit_id: str | None = None,
) -> dict:
    return {
        "name": name,
        "unit_id": unit_id,
    }


def test_register_and_get_factory():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    factory = registry.get_factory(
        "chapter"
    )

    assert factory is make_test_workflow


def test_register_normalizes_workflow_type():
    registry = WorkflowRegistry()

    registry.register(
        " Chapter ",
        make_test_workflow,
    )

    assert registry.contains(
        "chapter"
    )

    assert registry.contains(
        "CHAPTER"
    )

    assert registry.contains(
        " chapter "
    )


def test_build_calls_registered_factory():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    workflow = registry.build(
        "chapter",
        name="chapter-workflow",
        unit_id="unit-1",
    )

    assert workflow == {
        "name": "chapter-workflow",
        "unit_id": "unit-1",
    }


def test_duplicate_registration_raises():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    with pytest.raises(
        WorkflowAlreadyRegisteredError,
        match="이미 등록",
    ):
        registry.register(
            "CHAPTER",
            make_test_workflow,
        )


def test_register_can_replace_existing_factory():
    registry = WorkflowRegistry()

    def first_factory():
        return "first"

    def second_factory():
        return "second"

    registry.register(
        "chapter",
        first_factory,
    )

    registry.register(
        "chapter",
        second_factory,
        replace=True,
    )

    assert (
        registry.build("chapter")
        == "second"
    )


def test_unknown_workflow_raises():
    registry = WorkflowRegistry()

    with pytest.raises(
        WorkflowNotFoundError,
        match="등록되지 않은 Workflow",
    ):
        registry.get_factory(
            "missing"
        )


def test_unregister_removes_workflow():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    registry.unregister(
        "chapter"
    )

    assert not registry.contains(
        "chapter"
    )


def test_unregister_unknown_workflow_raises():
    registry = WorkflowRegistry()

    with pytest.raises(
        WorkflowNotFoundError,
    ):
        registry.unregister(
            "missing"
        )


def test_list_workflow_types_returns_sorted_names():
    registry = WorkflowRegistry()

    registry.register(
        "writer",
        make_test_workflow,
    )

    registry.register(
        "chapter",
        make_test_workflow,
    )

    registry.register(
        "book",
        make_test_workflow,
    )

    assert (
        registry.list_workflow_types()
        == [
            "book",
            "chapter",
            "writer",
        ]
    )


def test_contains_operator():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    assert "chapter" in registry
    assert "CHAPTER" in registry
    assert "missing" not in registry
    assert 123 not in registry


def test_len_returns_registration_count():
    registry = WorkflowRegistry()

    assert len(registry) == 0

    registry.register(
        "chapter",
        make_test_workflow,
    )

    assert len(registry) == 1


def test_clear_removes_all_workflows():
    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        make_test_workflow,
    )

    registry.register(
        "book",
        make_test_workflow,
    )

    registry.clear()

    assert len(registry) == 0
    assert (
        registry.list_workflow_types()
        == []
    )


def test_empty_workflow_type_raises():
    registry = WorkflowRegistry()

    with pytest.raises(
        ValueError,
        match="비어 있을 수 없습니다",
    ):
        registry.register(
            "   ",
            make_test_workflow,
        )


def test_non_callable_factory_raises():
    registry = WorkflowRegistry()

    with pytest.raises(
        ValueError,
        match="호출 가능한",
    ):
        registry.register(
            "chapter",
            "not-callable",  # type: ignore[arg-type]
        )


def test_default_registry_contains_chapter_workflow():
    from backend.orchestration.workflow_registry import (
        build_default_workflow_registry,
    )

    registry = (
        build_default_workflow_registry()
    )

    assert registry.contains(
        "chapter"
    )

    assert registry.contains(
        "technical_chapter"
    )


def test_default_registry_builds_chapter_workflow():
    from backend.orchestration.workflow_registry import (
        build_default_workflow_registry,
    )

    registry = (
        build_default_workflow_registry()
    )

    # build_chapter_workflow는 unit_id가 필수다.
    workflow = registry.build(
        "chapter",
        unit_id="unit-test",
    )

    assert workflow is not None
    assert len(workflow) > 0
    assert (
        workflow[0].stage_type
        == ProductionStageType.CHAPTER_PLANNING
    )
