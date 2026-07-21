from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel, UniqueConstraint

from backend.storage.model_utils import new_id, utc_now


class SourceCollectionType(StrEnum):
    DIRECTORY_UPLOAD = "DIRECTORY_UPLOAD"
    FILE_UPLOAD = "FILE_UPLOAD"
    URL_IMPORT = "URL_IMPORT"
    ZIP_UPLOAD = "ZIP_UPLOAD"
    MANUAL = "MANUAL"


class SourceCollectionStatus(StrEnum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    INDEXING = "INDEXING"
    ANALYZING = "ANALYZING"
    READY = "READY"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class SourceNodeType(StrEnum):
    DIRECTORY = "DIRECTORY"
    FILE = "FILE"


class SourceNodeStatus(StrEnum):
    PENDING = "PENDING"
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    READY = "READY"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class SourceUsageType(StrEnum):
    PRIMARY = "PRIMARY"
    REFERENCE = "REFERENCE"
    CODE = "CODE"
    DATA = "DATA"
    EXAMPLE = "EXAMPLE"
    VISUAL = "VISUAL"
    BACKGROUND = "BACKGROUND"


class SourceAssignmentType(StrEnum):
    PLANNER = "PLANNER"
    USER = "USER"
    RESEARCH_AGENT = "RESEARCH_AGENT"
    SYSTEM = "SYSTEM"


class SourceCollection(SQLModel, table=True):
    """
    자료 라이브러리에 등록된 파일 또는 폴더 묶음.

    특정 책에 직접 종속되지 않으며
    BookSourceCollection을 통해 여러 책과 연결됩니다.
    """

    __tablename__ = "source_collections"

    id: str = Field(
        default_factory=lambda: new_id("collection"),
        primary_key=True,
    )

    name: str = Field(index=True)
    description: str | None = None

    collection_type: str = Field(
        default=SourceCollectionType.DIRECTORY_UPLOAD.value,
        index=True,
    )

    status: str = Field(
        default=SourceCollectionStatus.CREATED.value,
        index=True,
    )

    root_name: str | None = None
    storage_path: str | None = None
    manifest_path: str | None = None

    total_files: int = 0
    supported_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    total_size_bytes: int = 0

    summary: str | None = None
    topics_json: str = "[]"
    missing_topics_json: str = "[]"
    metadata_json: str = "{}"

    content_hash: str | None = Field(
        default=None,
        index=True,
    )

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class SourceNode(SQLModel, table=True):
    """
    SourceCollection 내부 폴더 또는 파일 노드.

    FILE 노드인 경우 기존 SourceDocument와 연결할 수 있습니다.
    """

    __tablename__ = "source_nodes"

    __table_args__ = (
        UniqueConstraint(
            "collection_id",
            "relative_path",
            name="uq_source_node_collection_path",
        ),
    )

    id: str = Field(
        default_factory=lambda: new_id("source-node"),
        primary_key=True,
    )

    collection_id: str = Field(
        foreign_key="source_collections.id",
        index=True,
    )

    parent_id: str | None = Field(
        default=None,
        foreign_key="source_nodes.id",
        index=True,
    )

    node_type: str = Field(index=True)

    name: str
    relative_path: str = Field(index=True)

    depth: int = 0
    sort_order: int = 0

    document_id: str | None = Field(
        default=None,
        foreign_key="source_documents.source_id",
        index=True,
    )

    status: str = Field(
        default=SourceNodeStatus.PENDING.value,
        index=True,
    )

    mime_type: str | None = None
    extension: str | None = Field(
        default=None,
        index=True,
    )

    size_bytes: int = 0

    sha256: str | None = Field(
        default=None,
        index=True,
    )

    error_message: str | None = None
    metadata_json: str = "{}"

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class BookSourceCollection(SQLModel, table=True):
    """
    BookProject와 SourceCollection의 다대다 연결.

    하나의 Collection을 여러 책에서 재사용할 수 있습니다.
    """

    __tablename__ = "book_source_collections"

    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "collection_id",
            name="uq_book_source_collection",
        ),
    )

    id: str = Field(
        default_factory=lambda: new_id("book-source"),
        primary_key=True,
    )

    book_id: str = Field(
        foreign_key="book_projects.book_id",
        index=True,
    )

    collection_id: str = Field(
        foreign_key="source_collections.id",
        index=True,
    )

    enabled: bool = True

    purpose: str | None = None
    priority: int = 0

    linked_by: str = "USER"

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class UnitSourceLink(SQLModel, table=True):
    """
    BookUnit과 기존 SourceDocument의 연결.

    Planner가 추천하거나 사용자가 직접 설정할 수 있습니다.
    """

    __tablename__ = "unit_source_links"

    __table_args__ = (
        UniqueConstraint(
            "unit_id",
            "source_document_id",
            name="uq_unit_source_document",
        ),
    )

    id: str = Field(
        default_factory=lambda: new_id("unit-source"),
        primary_key=True,
    )

    unit_id: str = Field(
        foreign_key="book_units.unit_id",
        index=True,
    )

    source_document_id: str = Field(
        foreign_key="source_documents.source_id",
        index=True,
    )

    usage_type: str = Field(
        default=SourceUsageType.REFERENCE.value,
        index=True,
    )

    priority: int = 0
    required: bool = False
    enabled: bool = True

    assigned_by: str = Field(
        default=SourceAssignmentType.USER.value,
        index=True,
    )

    assignment_reason: str | None = None
    metadata_json: str = "{}"

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )
