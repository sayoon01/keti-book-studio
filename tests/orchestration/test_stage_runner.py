from __future__ import annotations

import pytest
from sqlmodel import Session

from backend.orchestration.context import (
    AgentContext,
    AgentContextBook,
    AgentContextRuntime,
)
from backend.orchestration.agent_schemas import AgentResult
from backend.orchestration.stage_runner import (
    StageExecutionFailedError,
    StageNotFoundError,
    StageNotRunnableError,
    StageRunResult,
    StageRunner,
)
from backend.storage.models_publishing import (
    AgentTask,
    ProductionRun,
    ProductionStage,
)


class FakeAgentRegistry:
    pass


class FakeContextBuilder:
    def build_for_task(
        self,
        *,
        task_id: str,
        include_full_text: bool = False,
    ) -> AgentContext:
        return AgentContext(
            runtime=AgentContextRuntime(
                run_id="run-test",
                stage_id="stage-test",
                task_id=task_id,
                workspace_id="workspace-test",
                stage_key="unit-1:plan",
                stage_type="CHAPTER_PLANNING",
                agent_role="PLANNER",
                agent_name="fake-planner",
            ),
            book=AgentContextBook(
                book_id="book-test",
                title="테스트 책",
            ),
        )


class FakeTaskService:
    pass


class FakeSuccessExecutionAdapter:
    def __init__(self, task: AgentTask) -> None:
        self.task = task

    def get_or_create_task(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> AgentTask:
        return self.task

    async def execute_task(
        self,
        *,
        task: AgentTask,
        context: AgentContext,
    ) -> AgentResult:
        return AgentResult.success(
            summary="테스트 성공",
        )

    def get_output_artifact_ids(
        self,
        *,
        task: AgentTask,
    ) -> list[str]:
        return ["artifact-plan-1"]


class FakeFailureExecutionAdapter:
    def __init__(self, task: AgentTask) -> None:
        self.task = task

    def get_or_create_task(
        self,
        *,
        run: ProductionRun,
        stage: ProductionStage,
    ) -> AgentTask:
        return self.task

    async def execute_task(
        self,
        *,
        task: AgentTask,
        context: AgentContext,
    ) -> AgentResult:
        return AgentResult.failed(
            summary="테스트 실패",
        )

    def get_output_artifact_ids(
        self,
        *,
        task: AgentTask,
    ) -> list[str]:
        return []


def create_run(
    session: Session,
    *,
    book_id: str,
) -> ProductionRun:
    run = ProductionRun(
        book_id=book_id,
        workspace_id="workspace-test",
        status="PENDING",
    )

    session.add(run)
    session.commit()
    session.refresh(run)

    return run


def create_stage(
    session: Session,
    *,
    run: ProductionRun,
    book_id: str,
    status: str = "PENDING",
) -> ProductionStage:
    stage = ProductionStage(
        run_id=run.run_id,
        book_id=book_id,
        stage_key="unit-1:plan",
        stage_type="CHAPTER_PLANNING",
        status=status,
        order_index=1,
    )

    session.add(stage)
    session.commit()
    session.refresh(stage)

    return stage


def create_task(
    session: Session,
    *,
    run: ProductionRun,
    stage: ProductionStage,
    book_id: str,
) -> AgentTask:
    task = AgentTask(
        run_id=run.run_id,
        stage_id=stage.stage_id,
        book_id=book_id,
        agent_role="PLANNER",
        agent_name="fake-planner",
        task_type="PLAN_CHAPTER",
        status="PENDING",
    )

    session.add(task)
    session.commit()
    session.refresh(task)

    return task


@pytest.mark.anyio
async def test_stage_runner_completes_stage(
    session: Session,
    prepared_book,
):
    run = create_run(
        session,
        book_id=prepared_book.book_id,
    )

    stage = create_stage(
        session,
        run=run,
        book_id=prepared_book.book_id,
    )

    task = create_task(
        session,
        run=run,
        stage=stage,
        book_id=prepared_book.book_id,
    )

    runner = StageRunner(
        session=session,
        agent_registry=FakeAgentRegistry(),  # type: ignore[arg-type]
        context_builder=FakeContextBuilder(),  # type: ignore[arg-type]
        task_service=FakeTaskService(),  # type: ignore[arg-type]
        execution_adapter=FakeSuccessExecutionAdapter(
            task
        ),
    )

    result = await runner.run_stage(
        stage_id=stage.stage_id
    )

    assert isinstance(result, StageRunResult)
    assert result.success is True
    assert result.status == "COMPLETED"
    assert result.output_artifact_ids == [
        "artifact-plan-1"
    ]

    session.refresh(stage)
    assert stage.status == "COMPLETED"


@pytest.mark.anyio
async def test_stage_runner_marks_stage_failed(
    session: Session,
    prepared_book,
):
    run = create_run(
        session,
        book_id=prepared_book.book_id,
    )

    stage = create_stage(
        session,
        run=run,
        book_id=prepared_book.book_id,
    )

    task = create_task(
        session,
        run=run,
        stage=stage,
        book_id=prepared_book.book_id,
    )

    runner = StageRunner(
        session=session,
        agent_registry=FakeAgentRegistry(),  # type: ignore[arg-type]
        context_builder=FakeContextBuilder(),  # type: ignore[arg-type]
        task_service=FakeTaskService(),  # type: ignore[arg-type]
        execution_adapter=FakeFailureExecutionAdapter(
            task
        ),
    )

    with pytest.raises(StageExecutionFailedError):
        await runner.run_stage(
            stage_id=stage.stage_id
        )

    session.refresh(stage)
    assert stage.status == "FAILED"


@pytest.mark.anyio
async def test_unknown_stage_raises(
    session: Session,
):
    runner = StageRunner(
        session=session,
        agent_registry=FakeAgentRegistry(),  # type: ignore[arg-type]
        context_builder=FakeContextBuilder(),  # type: ignore[arg-type]
        task_service=FakeTaskService(),  # type: ignore[arg-type]
        execution_adapter=FakeSuccessExecutionAdapter(
            task=None  # type: ignore[arg-type]
        ),
    )

    with pytest.raises(StageNotFoundError):
        await runner.run_stage(
            stage_id="missing-stage"
        )


@pytest.mark.anyio
async def test_completed_stage_cannot_run_again(
    session: Session,
    prepared_book,
):
    run = create_run(
        session,
        book_id=prepared_book.book_id,
    )

    stage = create_stage(
        session,
        run=run,
        book_id=prepared_book.book_id,
        status="COMPLETED",
    )

    task = create_task(
        session,
        run=run,
        stage=stage,
        book_id=prepared_book.book_id,
    )

    runner = StageRunner(
        session=session,
        agent_registry=FakeAgentRegistry(),  # type: ignore[arg-type]
        context_builder=FakeContextBuilder(),  # type: ignore[arg-type]
        task_service=FakeTaskService(),  # type: ignore[arg-type]
        execution_adapter=FakeSuccessExecutionAdapter(
            task
        ),
    )

    with pytest.raises(StageNotRunnableError):
        await runner.run_stage(
            stage_id=stage.stage_id
        )
