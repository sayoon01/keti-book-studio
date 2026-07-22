import pytest

from backend.orchestration.context import (
    AgentContext,
    AgentContextArtifact,
    AgentContextBook,
    AgentContextRuntime,
)
from backend.publishing.enums import (
    ProductionArtifactType,
)


def make_context(
    artifacts: list[AgentContextArtifact] | None = None,
) -> AgentContext:
    return AgentContext(
        runtime=AgentContextRuntime(
            run_id="run-test",
            stage_id="stage-test",
            task_id="task-test",
            workspace_id="workspace-test",
            stage_key="chapter-writing",
            stage_type="CHAPTER_WRITING",
            agent_role="WRITER",
            agent_name="chapter_writer",
        ),
        book=AgentContextBook(
            book_id="book-test",
            title="테스트 책",
        ),
        input_artifacts=artifacts or [],
    )


def test_get_artifacts_by_type_accepts_enum():
    context = make_context(
        artifacts=[
            AgentContextArtifact(
                artifact_id="artifact-plan-1",
                artifact_type="CHAPTER_PLAN",
                name="1장 계획",
                content={
                    "chapter_title": "1장",
                },
            ),
            AgentContextArtifact(
                artifact_id="artifact-research-1",
                artifact_type="RESEARCH_REPORT",
                name="1장 조사 보고서",
                content={
                    "topic": "1장",
                },
            ),
        ]
    )

    matches = context.get_artifacts_by_type(
        ProductionArtifactType.CHAPTER_PLAN
    )

    assert len(matches) == 1
    assert (
        matches[0].artifact_id
        == "artifact-plan-1"
    )


def test_get_artifacts_by_type_accepts_string():
    context = make_context(
        artifacts=[
            AgentContextArtifact(
                artifact_id="artifact-plan-1",
                artifact_type="CHAPTER_PLAN",
                name="1장 계획",
            ),
        ]
    )

    matches = context.get_artifacts_by_type(
        "CHAPTER_PLAN"
    )

    assert len(matches) == 1


def test_get_latest_artifact_returns_last_match():
    context = make_context(
        artifacts=[
            AgentContextArtifact(
                artifact_id="artifact-plan-v1",
                artifact_type="CHAPTER_PLAN",
                name="1장 계획 v1",
            ),
            AgentContextArtifact(
                artifact_id="artifact-draft",
                artifact_type="CHAPTER_DRAFT",
                name="1장 초안",
            ),
            AgentContextArtifact(
                artifact_id="artifact-plan-v2",
                artifact_type="CHAPTER_PLAN",
                name="1장 계획 v2",
            ),
        ]
    )

    latest = context.get_latest_artifact(
        ProductionArtifactType.CHAPTER_PLAN
    )

    assert latest is not None
    assert (
        latest.artifact_id
        == "artifact-plan-v2"
    )


def test_has_artifact_returns_true():
    context = make_context(
        artifacts=[
            AgentContextArtifact(
                artifact_id="artifact-research",
                artifact_type="RESEARCH_REPORT",
                name="조사 보고서",
            ),
        ]
    )

    assert context.has_artifact(
        ProductionArtifactType.RESEARCH_REPORT
    )


def test_has_artifact_returns_false():
    context = make_context()

    assert not context.has_artifact(
        ProductionArtifactType.RESEARCH_REPORT
    )


def test_require_artifact_returns_artifact():
    context = make_context(
        artifacts=[
            AgentContextArtifact(
                artifact_id="artifact-plan",
                artifact_type="CHAPTER_PLAN",
                name="챕터 계획",
            ),
        ]
    )

    artifact = context.require_artifact(
        ProductionArtifactType.CHAPTER_PLAN
    )

    assert (
        artifact.artifact_id
        == "artifact-plan"
    )


def test_require_artifact_raises_when_missing():
    context = make_context()

    with pytest.raises(
        ValueError,
        match="CHAPTER_PLAN",
    ):
        context.require_artifact(
            ProductionArtifactType.CHAPTER_PLAN
        )
