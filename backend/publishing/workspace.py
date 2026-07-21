from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.publishing.schemas import (
    PublishingWorkspace,
    WorkspaceArtifact,
    WorkspaceBookConfig,
    WorkspaceDecision,
    WorkspaceReviewIssue,
    WorkspaceSource,
    WorkspaceUnit,
)


class PlannerWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    sources: list[WorkspaceSource]

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )


class WriterWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit

    sources: list[WorkspaceSource]
    chapter_plan: WorkspaceArtifact | None = None

    previous_unit_summaries: list[str] = Field(
        default_factory=list
    )

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )

    role_persona: dict[str, Any] = Field(
        default_factory=dict
    )


class ReviewerWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit

    sources: list[WorkspaceSource]
    draft: WorkspaceArtifact

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )

    reviewer_role: str


class ReviserWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit

    draft: WorkspaceArtifact
    accepted_review_issues: list[WorkspaceReviewIssue]

    decisions: list[WorkspaceDecision] = Field(
        default_factory=list
    )

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )


class ReaderWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit

    revised_draft: WorkspaceArtifact
    reader_persona: dict[str, Any] = Field(
        default_factory=dict
    )


class EditorWorkspaceView(BaseModel):
    book: WorkspaceBookConfig
    unit: WorkspaceUnit

    artifacts: list[WorkspaceArtifact]
    review_issues: list[WorkspaceReviewIssue]
    decisions: list[WorkspaceDecision]

    book_policy: dict[str, Any] = Field(
        default_factory=dict
    )


def build_planner_view(
    workspace: PublishingWorkspace,
) -> PlannerWorkspaceView:
    return PlannerWorkspaceView(
        book=workspace.book,
        sources=workspace.sources,
        book_policy=workspace.book_policy,
    )


def build_writer_view(
    workspace: PublishingWorkspace,
) -> WriterWorkspaceView:
    if workspace.unit is None:
        raise ValueError(
            "Writer Workspace에는 unit이 필요합니다."
        )

    chapter_plan = _latest_artifact(
        workspace.artifacts,
        "CHAPTER_PLAN",
    )

    return WriterWorkspaceView(
        book=workspace.book,
        unit=workspace.unit,
        sources=workspace.sources,
        chapter_plan=chapter_plan,
        previous_unit_summaries=(
            workspace.previous_unit_summaries
        ),
        book_policy=workspace.book_policy,
        role_persona=workspace.role_persona,
    )


def build_reviewer_view(
    workspace: PublishingWorkspace,
    *,
    reviewer_role: str,
) -> ReviewerWorkspaceView:
    if workspace.unit is None:
        raise ValueError(
            "Reviewer Workspace에는 unit이 필요합니다."
        )

    draft = _latest_artifact(
        workspace.artifacts,
        "CHAPTER_DRAFT",
    )

    if not draft:
        raise ValueError(
            "검토할 CHAPTER_DRAFT가 없습니다."
        )

    return ReviewerWorkspaceView(
        book=workspace.book,
        unit=workspace.unit,
        sources=workspace.sources,
        draft=draft,
        book_policy=workspace.book_policy,
        reviewer_role=reviewer_role,
    )


def build_reviser_view(
    workspace: PublishingWorkspace,
) -> ReviserWorkspaceView:
    if workspace.unit is None:
        raise ValueError(
            "Reviser Workspace에는 unit이 필요합니다."
        )

    draft = _latest_artifact(
        workspace.artifacts,
        "CHAPTER_DRAFT",
    )

    if not draft:
        raise ValueError(
            "수정할 CHAPTER_DRAFT가 없습니다."
        )

    accepted_issues = [
        issue
        for issue in workspace.review_issues
        if issue.status in {
            "ACCEPTED",
            "APPROVED",
            "OPEN",
        }
    ]

    return ReviserWorkspaceView(
        book=workspace.book,
        unit=workspace.unit,
        draft=draft,
        accepted_review_issues=accepted_issues,
        decisions=workspace.decisions,
        book_policy=workspace.book_policy,
    )


def build_reader_view(
    workspace: PublishingWorkspace,
    *,
    reader_persona: dict[str, Any],
) -> ReaderWorkspaceView:
    if workspace.unit is None:
        raise ValueError(
            "Reader Workspace에는 unit이 필요합니다."
        )

    revised_draft = (
        _latest_artifact(
            workspace.artifacts,
            "REVISED_CHAPTER",
        )
        or _latest_artifact(
            workspace.artifacts,
            "CHAPTER_DRAFT",
        )
    )

    if not revised_draft:
        raise ValueError(
            "Reader가 평가할 챕터가 없습니다."
        )

    return ReaderWorkspaceView(
        book=workspace.book,
        unit=workspace.unit,
        revised_draft=revised_draft,
        reader_persona=reader_persona,
    )


def build_editor_view(
    workspace: PublishingWorkspace,
) -> EditorWorkspaceView:
    if workspace.unit is None:
        raise ValueError(
            "Editor Workspace에는 unit이 필요합니다."
        )

    return EditorWorkspaceView(
        book=workspace.book,
        unit=workspace.unit,
        artifacts=workspace.artifacts,
        review_issues=workspace.review_issues,
        decisions=workspace.decisions,
        book_policy=workspace.book_policy,
    )


def _latest_artifact(
    artifacts: list[WorkspaceArtifact],
    artifact_type: str,
) -> WorkspaceArtifact | None:
    matched = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == artifact_type
    ]

    if not matched:
        return None

    return matched[-1]
