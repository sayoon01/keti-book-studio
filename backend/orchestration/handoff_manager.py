from __future__ import annotations

from sqlmodel import Session

from backend.storage.model_utils import (
    json_dumps,
    json_loads,
)
from backend.storage.models_publishing import (
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class HandoffManager:
    def __init__(self, session: Session):
        self.session = session

        self.repository = ProductionRepository(
            session
        )

    def handoff_stage_outputs(
        self,
        *,
        source_stage_id: str,
        target_stage_id: str,
        artifact_types: set[str] | None = None,
        replace: bool = False,
    ) -> list[str]:
        source_stage = (
            self._get_required_stage(
                source_stage_id
            )
        )

        target_stage = (
            self._get_required_stage(
                target_stage_id
            )
        )

        self._validate_stage_relation(
            source_stage,
            target_stage,
        )

        source_artifact_ids = json_loads(
            source_stage.output_artifact_ids_json,
            [],
        )

        if artifact_types:
            source_artifact_ids = (
                self._filter_artifact_ids(
                    source_artifact_ids,
                    artifact_types,
                )
            )

        if replace:
            target_artifact_ids = []
        else:
            target_artifact_ids = json_loads(
                target_stage
                .input_artifact_ids_json,
                [],
            )

        for artifact_id in source_artifact_ids:
            if (
                artifact_id
                not in target_artifact_ids
            ):
                target_artifact_ids.append(
                    artifact_id
                )

        target_stage.input_artifact_ids_json = (
            json_dumps(target_artifact_ids)
        )

        self.repository.save_stage(
            target_stage
        )

        return target_artifact_ids

    def handoff_dependencies(
        self,
        *,
        target_stage_id: str,
        artifact_types: set[str] | None = None,
    ) -> list[str]:
        target_stage = (
            self._get_required_stage(
                target_stage_id
            )
        )

        dependency_keys = json_loads(
            target_stage.depends_on_json,
            [],
        )

        merged_artifact_ids = json_loads(
            target_stage.input_artifact_ids_json,
            [],
        )

        for dependency_key in dependency_keys:
            source_stage = (
                self.repository
                .get_stage_by_key(
                    run_id=target_stage.run_id,
                    stage_key=dependency_key,
                )
            )

            if not source_stage:
                raise ValueError(
                    "선행 Stage를 찾을 수 "
                    f"없습니다: {dependency_key}"
                )

            artifact_ids = json_loads(
                source_stage
                .output_artifact_ids_json,
                [],
            )

            if artifact_types:
                artifact_ids = (
                    self._filter_artifact_ids(
                        artifact_ids,
                        artifact_types,
                    )
                )

            for artifact_id in artifact_ids:
                if (
                    artifact_id
                    not in merged_artifact_ids
                ):
                    merged_artifact_ids.append(
                        artifact_id
                    )

        target_stage.input_artifact_ids_json = (
            json_dumps(merged_artifact_ids)
        )

        self.repository.save_stage(
            target_stage
        )

        return merged_artifact_ids

    def attach_artifacts_to_task(
        self,
        *,
        stage_id: str,
        task_id: str,
    ) -> list[str]:
        stage = self._get_required_stage(
            stage_id
        )

        task = self.repository.get_task(
            task_id
        )

        if not task:
            raise ValueError(
                "AgentTask를 찾을 수 없습니다."
            )

        if task.stage_id != stage.stage_id:
            raise ValueError(
                "Task와 Stage가 일치하지 않습니다."
            )

        stage_artifact_ids = json_loads(
            stage.input_artifact_ids_json,
            [],
        )

        task_artifact_ids = json_loads(
            task.input_artifact_ids_json,
            [],
        )

        for artifact_id in stage_artifact_ids:
            if (
                artifact_id
                not in task_artifact_ids
            ):
                task_artifact_ids.append(
                    artifact_id
                )

        task.input_artifact_ids_json = (
            json_dumps(task_artifact_ids)
        )

        self.repository.save_task(task)

        return task_artifact_ids

    def _filter_artifact_ids(
        self,
        artifact_ids: list[str],
        artifact_types: set[str],
    ) -> list[str]:
        filtered: list[str] = []

        for artifact_id in artifact_ids:
            artifact = (
                self.repository
                .get_artifact(artifact_id)
            )

            if not artifact:
                continue

            if (
                artifact.artifact_type
                in artifact_types
            ):
                filtered.append(
                    artifact_id
                )

        return filtered

    def _get_required_stage(
        self,
        stage_id: str,
    ) -> ProductionStage:
        stage = self.repository.get_stage(
            stage_id
        )

        if not stage:
            raise ValueError(
                "ProductionStage를 찾을 수 "
                f"없습니다: {stage_id}"
            )

        return stage

    @staticmethod
    def _validate_stage_relation(
        source_stage: ProductionStage,
        target_stage: ProductionStage,
    ) -> None:
        if (
            source_stage.run_id
            != target_stage.run_id
        ):
            raise ValueError(
                "서로 다른 ProductionRun의 "
                "Stage는 연결할 수 없습니다."
            )

        if (
            source_stage.book_id
            != target_stage.book_id
        ):
            raise ValueError(
                "서로 다른 Book의 Stage는 "
                "연결할 수 없습니다."
            )
