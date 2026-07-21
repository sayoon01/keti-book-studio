from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceBookConfig(BaseModel):
    book_id: str
    title: str

    document_type: str | None = None
    target_reader: str | None = None
    purpose: str | None = None
    language: str | None = None

    automation_level: str = "BALANCED"
    workflow_type: str = "technical_book"

    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceUnit(BaseModel):
    unit_id: str
    title: str

    description: str | None = None
    order_index: int = 0
    status: str | None = None

    target_characters: int | None = None
    is_important: bool = False

    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSource(BaseModel):
    source_id: str
    title: str
    source_type: str

    collection_id: str | None = None
    node_id: str | None = None
    relative_path: str | None = None

    usage_type: str = "REFERENCE"
    priority: int = 0
    required: bool = False

    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)

    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceReviewIssue(BaseModel):
    issue_id: str
    category: str
    severity: str

    summary: str
    suggestion: str | None = None
    evidence: str | None = None

    status: str = "OPEN"
    reviewer_role: str | None = None


class WorkspaceDecision(BaseModel):
    decision_id: str
    decision_type: str

    status: str
    selected_option: str | None = None

    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkspaceArtifact(BaseModel):
    artifact_id: str
    artifact_type: str

    task_id: str | None = None
    agent_role: str | None = None
    unit_id: str | None = None

    content: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime | None = None


class PublishingWorkspace(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit | None = None

    sources: list[WorkspaceSource] = Field(
        default_factory=list
    )

    artifacts: list[WorkspaceArtifact] = Field(
        default_factory=list
    )

    review_issues: list[WorkspaceReviewIssue] = Field(
        default_factory=list
    )

    decisions: list[WorkspaceDecision] = Field(
        default_factory=list
    )

    previous_unit_summaries: list[str] = Field(
        default_factory=list
    )

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )

    role_persona: dict[str, Any] = Field(
        default_factory=dict
    )

    runtime_state: dict[str, Any] = Field(
        default_factory=dict
    )
