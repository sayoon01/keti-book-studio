from __future__ import annotations

from sqlmodel import Session, select

from backend.storage.model_utils import utc_now
from backend.storage.models_publishing import (
    AgentArtifactRecord,
    AgentMessage,
    AgentTask,
    ProductionRun,
    ProductionStage,
)


class ProductionRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------------------------------------------------------
    # ProductionRun
    # ---------------------------------------------------------

    def add_run(
        self,
        run: ProductionRun,
    ) -> ProductionRun:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(
        self,
        run_id: str,
    ) -> ProductionRun | None:
        return self.session.get(
            ProductionRun,
            run_id,
        )

    def save_run(
        self,
        run: ProductionRun,
    ) -> ProductionRun:
        run.updated_at = utc_now()

        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def list_runs_for_book(
        self,
        book_id: str,
        *,
        limit: int = 50,
    ) -> list[ProductionRun]:
        statement = (
            select(ProductionRun)
            .where(ProductionRun.book_id == book_id)
            .order_by(ProductionRun.created_at.desc())
            .limit(limit)
        )

        return list(self.session.exec(statement).all())

    # ---------------------------------------------------------
    # ProductionStage
    # ---------------------------------------------------------

    def add_stage(
        self,
        stage: ProductionStage,
    ) -> ProductionStage:
        self.session.add(stage)
        self.session.commit()
        self.session.refresh(stage)
        return stage

    def add_stages(
        self,
        stages: list[ProductionStage],
    ) -> list[ProductionStage]:
        self.session.add_all(stages)
        self.session.commit()

        for stage in stages:
            self.session.refresh(stage)

        return stages

    def get_stage(
        self,
        stage_id: str,
    ) -> ProductionStage | None:
        return self.session.get(
            ProductionStage,
            stage_id,
        )

    def get_stage_by_key(
        self,
        *,
        run_id: str,
        stage_key: str,
    ) -> ProductionStage | None:
        statement = select(ProductionStage).where(
            ProductionStage.run_id == run_id,
            ProductionStage.stage_key == stage_key,
        )

        return self.session.exec(statement).first()

    def list_stages(
        self,
        run_id: str,
    ) -> list[ProductionStage]:
        statement = (
            select(ProductionStage)
            .where(ProductionStage.run_id == run_id)
            .order_by(
                ProductionStage.order_index,
                ProductionStage.created_at,
            )
        )

        return list(self.session.exec(statement).all())

    def save_stage(
        self,
        stage: ProductionStage,
    ) -> ProductionStage:
        stage.updated_at = utc_now()

        self.session.add(stage)
        self.session.commit()
        self.session.refresh(stage)
        return stage

    # ---------------------------------------------------------
    # AgentTask
    # ---------------------------------------------------------

    def add_task(
        self,
        task: AgentTask,
    ) -> AgentTask:
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def add_tasks(
        self,
        tasks: list[AgentTask],
    ) -> list[AgentTask]:
        self.session.add_all(tasks)
        self.session.commit()

        for task in tasks:
            self.session.refresh(task)

        return tasks

    def get_task(
        self,
        task_id: str,
    ) -> AgentTask | None:
        return self.session.get(
            AgentTask,
            task_id,
        )

    def list_tasks_for_stage(
        self,
        stage_id: str,
    ) -> list[AgentTask]:
        statement = (
            select(AgentTask)
            .where(AgentTask.stage_id == stage_id)
            .order_by(
                AgentTask.priority.desc(),
                AgentTask.created_at,
            )
        )

        return list(self.session.exec(statement).all())

    def list_tasks_for_run(
        self,
        run_id: str,
    ) -> list[AgentTask]:
        statement = (
            select(AgentTask)
            .where(AgentTask.run_id == run_id)
            .order_by(AgentTask.created_at)
        )

        return list(self.session.exec(statement).all())

    def save_task(
        self,
        task: AgentTask,
    ) -> AgentTask:
        task.updated_at = utc_now()

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    # ---------------------------------------------------------
    # Artifact
    # ---------------------------------------------------------

    def add_artifact(
        self,
        artifact: AgentArtifactRecord,
    ) -> AgentArtifactRecord:
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def get_artifact(
        self,
        artifact_id: str,
    ) -> AgentArtifactRecord | None:
        return self.session.get(
            AgentArtifactRecord,
            artifact_id,
        )

    def list_artifacts_for_run(
        self,
        run_id: str,
    ) -> list[AgentArtifactRecord]:
        statement = (
            select(AgentArtifactRecord)
            .where(
                AgentArtifactRecord.run_id == run_id
            )
            .order_by(
                AgentArtifactRecord.created_at
            )
        )

        return list(self.session.exec(statement).all())

    def list_artifacts_for_stage(
        self,
        stage_id: str,
    ) -> list[AgentArtifactRecord]:
        statement = (
            select(AgentArtifactRecord)
            .where(
                AgentArtifactRecord.stage_id == stage_id
            )
            .order_by(
                AgentArtifactRecord.created_at
            )
        )

        return list(self.session.exec(statement).all())

    def list_artifacts_for_unit(
        self,
        *,
        run_id: str,
        unit_id: str,
    ) -> list[AgentArtifactRecord]:
        statement = (
            select(AgentArtifactRecord)
            .where(
                AgentArtifactRecord.run_id == run_id,
                AgentArtifactRecord.unit_id == unit_id,
            )
            .order_by(
                AgentArtifactRecord.created_at
            )
        )

        return list(self.session.exec(statement).all())

    def get_latest_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        unit_id: str | None = None,
    ) -> AgentArtifactRecord | None:
        statement = select(
            AgentArtifactRecord
        ).where(
            AgentArtifactRecord.run_id == run_id,
            AgentArtifactRecord.artifact_type
            == artifact_type,
        )

        if unit_id is not None:
            statement = statement.where(
                AgentArtifactRecord.unit_id == unit_id
            )

        statement = statement.order_by(
            AgentArtifactRecord.created_at.desc()
        )

        return self.session.exec(statement).first()

    # ---------------------------------------------------------
    # AgentMessage
    # ---------------------------------------------------------

    def add_message(
        self,
        message: AgentMessage,
    ) -> AgentMessage:
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def list_messages_for_run(
        self,
        run_id: str,
    ) -> list[AgentMessage]:
        statement = (
            select(AgentMessage)
            .where(AgentMessage.run_id == run_id)
            .order_by(AgentMessage.created_at)
        )

        return list(self.session.exec(statement).all())

    def list_unresolved_messages(
        self,
        run_id: str,
    ) -> list[AgentMessage]:
        statement = (
            select(AgentMessage)
            .where(
                AgentMessage.run_id == run_id,
                AgentMessage.resolved.is_(False),
            )
            .order_by(
                AgentMessage.blocking.desc(),
                AgentMessage.created_at,
            )
        )

        return list(self.session.exec(statement).all())
