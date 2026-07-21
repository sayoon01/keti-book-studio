from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class SourceCollectionRead(BaseModel):
    id: str
    name: str
    description: str | None

    collection_type: str
    status: str
    root_name: str | None

    total_files: int
    supported_files: int
    skipped_files: int
    failed_files: int
    total_size_bytes: int

    summary: str | None
    created_at: datetime
    updated_at: datetime


class SourceNodeRead(BaseModel):
    id: str
    collection_id: str
    parent_id: str | None

    node_type: str
    name: str
    relative_path: str
    depth: int

    document_id: str | None
    status: str

    mime_type: str | None
    extension: str | None
    size_bytes: int
    sha256: str | None
    error_message: str | None


class SourceTreeNode(BaseModel):
    id: str
    node_type: str
    name: str
    relative_path: str
    status: str

    document_id: str | None = None
    size_bytes: int = 0
    extension: str | None = None
    error_message: str | None = None

    children: list["SourceTreeNode"] = Field(default_factory=list)


class SourceCollectionTreeResponse(BaseModel):
    collection: SourceCollectionRead
    roots: list[SourceTreeNode]


class LinkCollectionToBookRequest(BaseModel):
    purpose: str | None = None
    priority: int = 0


class BookSourceCollectionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    book_id: str
    collection_id: str
    enabled: bool
    purpose: str | None
    priority: int
    linked_by: str
    created_at: datetime
    updated_at: datetime


class UnitSourceLinkCreate(BaseModel):
    source_document_id: str
    usage_type: str = "REFERENCE"
    priority: int = 0
    required: bool = False
    assignment_reason: str | None = None


class UnitSourceLinkRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    unit_id: str
    source_document_id: str
    usage_type: str
    priority: int
    required: bool
    enabled: bool
    assigned_by: str
    assignment_reason: str | None
    created_at: datetime
    updated_at: datetime


class DirectoryUploadResult(BaseModel):
    collection: SourceCollectionRead
    uploaded_files: int
    skipped_files: int
    failed_files: int
    warnings: list[str] = Field(default_factory=list)


class ApiMessage(BaseModel):
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AnalyzeCollectionRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    book_id: str | None = None


class AnalyzeCollectionResponse(BaseModel):
    collection_id: str
    total_files: int
    completed_files: int
    skipped_files: int
    failed_files: int
    document_ids: list[str]
    warnings: list[str] = Field(default_factory=list)


SourceTreeNode.model_rebuild()
