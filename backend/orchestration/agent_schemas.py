from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    WAITING = "WAITING"
    SKIPPED = "SKIPPED"


class AgentRequestType(StrEnum):
    EXECUTE = "EXECUTE"
    RETRY = "RETRY"
    RESUME = "RESUME"
    REVIEW = "REVIEW"
    REVISE = "REVISE"


class AgentProposalType(StrEnum):
    NONE = "NONE"
    USER_DECISION = "USER_DECISION"
    RETRY = "RETRY"
    SKIP_STAGE = "SKIP_STAGE"
    CHANGE_WORKFLOW = "CHANGE_WORKFLOW"
    REQUEST_SOURCE = "REQUEST_SOURCE"


class AgentArtifact(BaseModel):
    """
    Agent가 생성한 논리적 결과물입니다.

    아직 DB 객체가 아니라 메모리 상의 결과이며,
    ArtifactService가 AgentArtifactRecord로 저장합니다.
    """

    artifact_type: str

    name: str

    content: dict[str, Any] = Field(
        default_factory=dict
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    storage_type: str = "DATABASE"

    storage_path: str | None = None


class AgentRequest(BaseModel):
    request_type: AgentRequestType = (
        AgentRequestType.EXECUTE
    )

    instruction: str | None = None

    input_data: dict[str, Any] = Field(
        default_factory=dict
    )

    input_artifact_ids: list[str] = Field(
        default_factory=list
    )

    runtime_options: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentProposal(BaseModel):
    proposal_type: AgentProposalType = (
        AgentProposalType.NONE
    )

    title: str | None = None
    message: str | None = None

    blocking: bool = False

    payload: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentUsage(BaseModel):
    model_name: str | None = None

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    latency_ms: int = 0


class AgentResult(BaseModel):
    status: AgentExecutionStatus

    summary: str = ""

    artifacts: list[AgentArtifact] = Field(
        default_factory=list
    )

    proposals: list[AgentProposal] = Field(
        default_factory=list
    )

    output_data: dict[str, Any] = Field(
        default_factory=dict
    )

    runtime_state: dict[str, Any] = Field(
        default_factory=dict
    )

    usage: AgentUsage = Field(
        default_factory=AgentUsage
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )

    @classmethod
    def success(
        cls,
        *,
        summary: str = "",
        artifacts: list[AgentArtifact] | None = None,
        output_data: dict[str, Any] | None = None,
        runtime_state: dict[str, Any] | None = None,
        usage: AgentUsage | None = None,
        warnings: list[str] | None = None,
    ) -> "AgentResult":
        return cls(
            status=AgentExecutionStatus.SUCCESS,
            summary=summary,
            artifacts=artifacts or [],
            output_data=output_data or {},
            runtime_state=runtime_state or {},
            usage=usage or AgentUsage(),
            warnings=warnings or [],
        )

    @classmethod
    def failed(
        cls,
        *,
        summary: str,
        errors: list[str] | None = None,
        runtime_state: dict[str, Any] | None = None,
    ) -> "AgentResult":
        return cls(
            status=AgentExecutionStatus.FAILED,
            summary=summary,
            errors=errors or [summary],
            runtime_state=runtime_state or {},
        )
