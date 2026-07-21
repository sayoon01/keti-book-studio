from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.schemas import AgentRequest


class AgentContextArtifact(BaseModel):
    artifact_id: str

    artifact_type: str
    name: str

    content: dict[str, Any] = Field(
        default_factory=dict
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    created_by_role: str | None = None


class AgentContextSource(BaseModel):
    source_id: str

    title: str
    source_type: str

    text_content: str = ""

    summary: str | None = None

    keywords: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextUnit(BaseModel):
    unit_id: str

    title: str
    description: str | None = None

    order_index: int = 0

    status: str | None = None

    target_length: int | None = None

    required_topics: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextBook(BaseModel):
    book_id: str

    title: str

    description: str | None = None
    target_reader: str | None = None
    purpose: str | None = None
    language: str = "ko"

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextPolicy(BaseModel):
    persona_name: str | None = None

    common_instruction: str = ""
    role_instruction: str = ""

    writing_style: str | None = None
    review_policy: str | None = None
    visual_policy: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextRuntime(BaseModel):
    run_id: str
    stage_id: str
    task_id: str

    workspace_id: str

    stage_key: str
    stage_type: str

    agent_role: str
    agent_name: str

    attempt: int = 1
    max_retries: int = 1

    automation_level: str = "BALANCED"

    runtime_state: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContext(BaseModel):
    runtime: AgentContextRuntime

    book: AgentContextBook

    unit: AgentContextUnit | None = None

    request: AgentRequest = Field(
        default_factory=AgentRequest
    )

    policy: AgentContextPolicy = Field(
        default_factory=AgentContextPolicy
    )

    sources: list[AgentContextSource] = Field(
        default_factory=list
    )

    input_artifacts: list[
        AgentContextArtifact
    ] = Field(
        default_factory=list
    )

    shared_state: dict[str, Any] = Field(
        default_factory=dict
    )

    def get_artifacts_by_type(
        self,
        artifact_type: str,
    ) -> list[AgentContextArtifact]:
        return [
            artifact
            for artifact in self.input_artifacts
            if artifact.artifact_type
            == artifact_type
        ]

    def get_latest_artifact(
        self,
        artifact_type: str,
    ) -> AgentContextArtifact | None:
        matches = self.get_artifacts_by_type(
            artifact_type
        )

        if not matches:
            return None

        return matches[-1]
