from __future__ import annotations

import hashlib
from typing import Any

from sqlmodel import Session

from backend.orchestration.context import (
    AgentContextArtifact,
)
from backend.orchestration.agent_schemas import AgentArtifact
from backend.storage.model_utils import (
    json_dumps,
    json_loads,
)
from backend.storage.models_publishing import (
    AgentArtifactRecord,
    AgentTask,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class ArtifactService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProductionRepository(
            session
        )

    def create_artifact(
        self,
        *,
        run_id: str,
        book_id: str,
        artifact: AgentArtifact,
        stage_id: str | None = None,
        task_id: str | None = None,
        unit_id: str | None = None,
        created_by_role: str | None = None,
    ) -> AgentArtifactRecord:
        content_json = json_dumps(
            artifact.content
        )

        content_hash = self._create_hash(
            content_json
        )

        version = self._next_version(
            run_id=run_id,
            unit_id=unit_id,
            artifact_type=artifact.artifact_type,
        )

        record = AgentArtifactRecord(
            run_id=run_id,
            stage_id=stage_id,
            task_id=task_id,
            book_id=book_id,
            unit_id=unit_id,
            artifact_type=(
                artifact.artifact_type
            ),
            name=artifact.name,
            version=version,
            content_json=content_json,
            metadata_json=json_dumps(
                artifact.metadata
            ),
            storage_type=(
                artifact.storage_type
            ),
            storage_path=(
                artifact.storage_path
            ),
            content_hash=content_hash,
            created_by_role=created_by_role,
        )

        record = self.repository.add_artifact(
            record
        )

        if stage_id:
            self._append_stage_output(
                stage_id,
                record.artifact_id,
            )

        if task_id:
            self._append_task_output(
                task_id,
                record.artifact_id,
            )

        return record

    def create_many(
        self,
        *,
        run_id: str,
        book_id: str,
        artifacts: list[AgentArtifact],
        stage_id: str | None = None,
        task_id: str | None = None,
        unit_id: str | None = None,
        created_by_role: str | None = None,
    ) -> list[AgentArtifactRecord]:
        return [
            self.create_artifact(
                run_id=run_id,
                book_id=book_id,
                artifact=artifact,
                stage_id=stage_id,
                task_id=task_id,
                unit_id=unit_id,
                created_by_role=(
                    created_by_role
                ),
            )
            for artifact in artifacts
        ]

    def get_context_artifact(
        self,
        artifact_id: str,
    ) -> AgentContextArtifact:
        record = self.repository.get_artifact(
            artifact_id
        )

        if not record:
            raise ValueError(
                "Artifact를 찾을 수 없습니다: "
                f"{artifact_id}"
            )

        return self._to_context_artifact(
            record
        )

    def get_context_artifacts(
        self,
        artifact_ids: list[str],
    ) -> list[AgentContextArtifact]:
        return [
            self.get_context_artifact(
                artifact_id
            )
            for artifact_id in artifact_ids
        ]

    def get_stage_output_artifacts(
        self,
        stage_id: str,
    ) -> list[AgentContextArtifact]:
        records = (
            self.repository
            .list_artifacts_for_stage(
                stage_id
            )
        )

        return [
            self._to_context_artifact(record)
            for record in records
        ]

    def _append_stage_output(
        self,
        stage_id: str,
        artifact_id: str,
    ) -> None:
        stage = self.repository.get_stage(
            stage_id
        )

        if not stage:
            raise ValueError(
                "ProductionStage를 찾을 수 "
                f"없습니다: {stage_id}"
            )

        artifact_ids = json_loads(
            stage.output_artifact_ids_json,
            [],
        )

        if artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)

        stage.output_artifact_ids_json = (
            json_dumps(artifact_ids)
        )

        self.repository.save_stage(stage)

    def _append_task_output(
        self,
        task_id: str,
        artifact_id: str,
    ) -> None:
        task = self.repository.get_task(
            task_id
        )

        if not task:
            raise ValueError(
                "AgentTask를 찾을 수 없습니다: "
                f"{task_id}"
            )

        artifact_ids = json_loads(
            task.output_artifact_ids_json,
            [],
        )

        if artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)

        task.output_artifact_ids_json = (
            json_dumps(artifact_ids)
        )

        self.repository.save_task(task)

    def _next_version(
        self,
        *,
        run_id: str,
        unit_id: str | None,
        artifact_type: str,
    ) -> int:
        records = (
            self.repository
            .list_artifacts_for_run(run_id)
        )

        matching_versions = [
            record.version
            for record in records
            if (
                record.artifact_type
                == artifact_type
                and record.unit_id == unit_id
            )
        ]

        if not matching_versions:
            return 1

        return max(matching_versions) + 1

    def _to_context_artifact(
        self,
        record: AgentArtifactRecord,
    ) -> AgentContextArtifact:
        return AgentContextArtifact(
            artifact_id=record.artifact_id,
            artifact_type=(
                record.artifact_type
            ),
            name=record.name,
            content=json_loads(
                record.content_json,
                {},
            ),
            metadata=json_loads(
                record.metadata_json,
                {},
            ),
            created_by_role=(
                record.created_by_role
            ),
        )

    @staticmethod
    def _create_hash(
        content_json: str,
    ) -> str:
        return hashlib.sha256(
            content_json.encode("utf-8")
        ).hexdigest()
