from __future__ import annotations

from sqlmodel import Session

from backend.orchestration.context import (
    AgentContext,
    AgentContextBook,
    AgentContextPolicy,
    AgentContextRuntime,
    AgentContextSource,
    AgentContextUnit,
)
from backend.services.artifact_service import (
    ArtifactService,
)
from backend.services.workspace_service import (
    WorkspaceService,
)
from backend.storage.model_utils import json_loads
from backend.storage.models_publishing import (
    AgentTask,
    ProductionStage,
)
from backend.storage.repositories.production_repository import (
    ProductionRepository,
)


class AgentContextBuilder:
    """
    AgentTask / ProductionStage / Workspace를 합쳐
    AgentContext를 구성합니다.

    이전 Stage에서 Handoff된 Artifact ID를
    input_artifacts에 순서대로 넣습니다.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = ProductionRepository(
            session
        )
        self.artifact_service = ArtifactService(
            session
        )
        self.workspace_service = WorkspaceService(
            session
        )

    def build_for_task(
        self,
        *,
        task_id: str,
        include_full_text: bool = False,
    ) -> AgentContext:
        task = self.repository.get_task(task_id)

        if not task:
            raise ValueError(
                "AgentTask를 찾을 수 없습니다."
            )

        stage = self.repository.get_stage(
            task.stage_id
        )

        if not stage:
            raise ValueError(
                "ProductionStage를 찾을 수 없습니다."
            )

        run = self.repository.get_run(task.run_id)

        if not run:
            raise ValueError(
                "ProductionRun을 찾을 수 없습니다."
            )

        workspace = (
            self.workspace_service.build_workspace(
                book_id=task.book_id,
                unit_id=task.unit_id,
                include_full_text=include_full_text,
            )
        )

        input_artifact_ids = (
            self._resolve_input_artifact_ids(
                task=task,
                stage=stage,
            )
        )

        input_artifacts = (
            self.artifact_service
            .get_context_artifacts(
                input_artifact_ids
            )
        )

        unit_context = None

        if workspace.unit is not None:
            unit = workspace.unit
            unit_context = AgentContextUnit(
                unit_id=unit.unit_id,
                title=unit.title,
                description=unit.description,
                order_index=unit.order_index,
                status=unit.status,
                target_length=unit.target_characters,
                metadata=dict(unit.metadata),
            )

        return AgentContext(
            runtime=AgentContextRuntime(
                run_id=task.run_id,
                stage_id=task.stage_id,
                task_id=task.task_id,
                workspace_id=run.workspace_id,
                stage_key=stage.stage_key,
                stage_type=stage.stage_type,
                agent_role=task.agent_role,
                agent_name=task.agent_name,
                attempt=max(task.attempt, 1),
                max_retries=task.max_retries,
                automation_level=(
                    workspace.book.automation_level
                ),
            ),
            book=AgentContextBook(
                book_id=workspace.book.book_id,
                title=workspace.book.title,
                description=None,
                target_reader=(
                    workspace.book.target_reader
                ),
                purpose=workspace.book.purpose,
                language=(
                    workspace.book.language or "ko"
                ),
                metadata=dict(
                    workspace.book.metadata
                ),
            ),
            unit=unit_context,
            policy=AgentContextPolicy(
                metadata=dict(
                    workspace.book_policy
                ),
            ),
            sources=[
                AgentContextSource(
                    source_id=source.source_id,
                    title=source.title,
                    source_type=source.source_type,
                    text_content=(
                        source.extracted_text or ""
                    ),
                    summary=source.summary,
                    keywords=list(source.keywords),
                    metadata=dict(source.metadata),
                )
                for source in workspace.sources
            ],
            input_artifacts=input_artifacts,
            shared_state={},
        )

    def _resolve_input_artifact_ids(
        self,
        *,
        task: AgentTask,
        stage: ProductionStage,
    ) -> list[str]:
        task_ids = json_loads(
            task.input_artifact_ids_json,
            [],
        )

        if task_ids:
            return list(task_ids)

        return list(
            json_loads(
                stage.input_artifact_ids_json,
                [],
            )
        )
