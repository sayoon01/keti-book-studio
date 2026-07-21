from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from backend.publishing.enums import (
    AgentTaskStatus,
    ProductionRunStatus,
    ProductionStageStatus,
)
from backend.storage.model_utils import new_id, utc_now


class ProductionRun(SQLModel, table=True):
    __tablename__ = "production_runs"

    run_id: str = Field(
        default_factory=lambda: new_id("run"),
        primary_key=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    workspace_id: str = Field(index=True)

    workflow_type: str = Field(
        default="technical_book",
        index=True,
    )

    automation_level: str = Field(
        default="BALANCED",
        index=True,
    )

    status: str = Field(
        default=ProductionRunStatus.PENDING.value,
        index=True,
    )

    current_stage_id: Optional[str] = Field(
        default=None,
        index=True,
    )

    requested_by: Optional[str] = Field(
        default=None,
        index=True,
    )

    input_json: str = "{}"
    runtime_state_json: str = "{}"
    result_json: str = "{}"
    error_json: str = "{}"

    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProductionStage(SQLModel, table=True):
    __tablename__ = "production_stages"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "stage_key",
            name="uq_production_stage_run_key",
        ),
    )

    stage_id: str = Field(
        default_factory=lambda: new_id("stage"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: Optional[str] = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    stage_key: str = Field(index=True)
    stage_type: str = Field(index=True)

    order_index: int = Field(default=0, index=True)

    status: str = Field(
        default=ProductionStageStatus.PENDING.value,
        index=True,
    )

    depends_on_json: str = "[]"

    input_artifact_ids_json: str = "[]"
    output_artifact_ids_json: str = "[]"

    input_json: str = "{}"
    output_json: str = "{}"
    runtime_state_json: str = "{}"
    error_json: str = "{}"

    retry_count: int = 0
    max_retries: int = 1

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentTask(SQLModel, table=True):
    __tablename__ = "agent_tasks"

    task_id: str = Field(
        default_factory=lambda: new_id("task"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    stage_id: str = Field(
        foreign_key="production_stages.stage_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: Optional[str] = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    agent_role: str = Field(index=True)
    agent_name: str = Field(index=True)

    task_type: str = Field(index=True)

    status: str = Field(
        default=AgentTaskStatus.PENDING.value,
        index=True,
    )

    priority: int = Field(default=0, index=True)

    input_artifact_ids_json: str = "[]"
    output_artifact_ids_json: str = "[]"

    input_json: str = "{}"
    output_json: str = "{}"
    runtime_state_json: str = "{}"
    error_json: str = "{}"

    attempt: int = 0
    max_retries: int = 1

    model_name: Optional[str] = None

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    latency_ms: int = 0

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentArtifactRecord(SQLModel, table=True):
    __tablename__ = "agent_artifacts"

    artifact_id: str = Field(
        default_factory=lambda: new_id("artifact"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    stage_id: Optional[str] = Field(
        default=None,
        foreign_key="production_stages.stage_id",
        index=True,
    )

    task_id: Optional[str] = Field(
        default=None,
        foreign_key="agent_tasks.task_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: Optional[str] = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    artifact_type: str = Field(index=True)
    name: str

    version: int = 1

    content_json: str = "{}"
    metadata_json: str = "{}"

    storage_type: str = "DATABASE"
    storage_path: Optional[str] = None

    content_hash: Optional[str] = Field(
        default=None,
        index=True,
    )

    created_by_role: Optional[str] = Field(
        default=None,
        index=True,
    )

    created_at: datetime = Field(default_factory=utc_now)


class PublishingEvent(SQLModel, table=True):
    __tablename__ = "publishing_events"

    event_id: str = Field(
        default_factory=lambda: new_id("event"),
        primary_key=True,
    )

    run_id: Optional[str] = Field(
        default=None,
        foreign_key="production_runs.run_id",
        index=True,
    )

    stage_id: Optional[str] = Field(
        default=None,
        foreign_key="production_stages.stage_id",
        index=True,
    )

    task_id: Optional[str] = Field(
        default=None,
        foreign_key="agent_tasks.task_id",
        index=True,
    )

    book_id: Optional[str] = Field(
        default=None,
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: Optional[str] = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    event_type: str = Field(index=True)
    actor_type: str = Field(default="SYSTEM", index=True)
    actor_id: Optional[str] = Field(default=None, index=True)

    title: str
    message: Optional[str] = None

    payload_json: str = "{}"

    severity: str = Field(default="INFO", index=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        index=True,
    )


class AgentMessage(SQLModel, table=True):
    __tablename__ = "agent_messages"

    message_id: str = Field(
        default_factory=lambda: new_id("message"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    stage_id: Optional[str] = Field(
        default=None,
        foreign_key="production_stages.stage_id",
        index=True,
    )

    task_id: Optional[str] = Field(
        default=None,
        foreign_key="agent_tasks.task_id",
        index=True,
    )

    sender_role: str = Field(index=True)
    receiver_role: str = Field(index=True)

    message_type: str = Field(index=True)
    subject: str

    payload_json: str = "{}"

    blocking: bool = False
    resolved: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class ReviewIssue(SQLModel, table=True):
    __tablename__ = "review_issues"

    id: str = Field(
        default_factory=lambda: new_id("review-issue"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    task_id: str = Field(
        foreign_key="agent_tasks.task_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: str = Field(
        foreign_key="book_units.unit_id",
        index=True,
    )

    reviewer_role: str = Field(index=True)
    reviewer_persona_id: str | None = None

    category: str = Field(index=True)
    severity: str = Field(index=True)

    title: str
    description: str
    suggestion: str | None = None
    evidence: str | None = None
    section_key: str | None = None

    status: str = Field(default="OPEN", index=True)
    decision_reason: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class UserDecision(SQLModel, table=True):
    __tablename__ = "user_decisions"

    id: str = Field(
        default_factory=lambda: new_id("decision"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: str | None = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    decision_type: str = Field(index=True)
    target_type: str
    target_id: str

    status: str = Field(default="PENDING", index=True)
    options_json: str = "[]"

    selected_option: str | None = None
    instruction: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None


class ReaderSimulation(SQLModel, table=True):
    __tablename__ = "reader_simulations"

    id: str = Field(
        default_factory=lambda: new_id("reader-test"),
        primary_key=True,
    )

    run_id: str = Field(
        foreign_key="production_runs.run_id",
        index=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    unit_id: str | None = Field(
        default=None,
        foreign_key="book_units.unit_id",
        index=True,
    )

    reader_persona_id: str = Field(index=True)

    understanding_score: float
    completion_score: float

    confusing_sections_json: str = "[]"
    expected_questions_json: str = "[]"
    recommendations_json: str = "[]"

    is_final_book_review: bool = False

    created_at: datetime = Field(default_factory=utc_now)
