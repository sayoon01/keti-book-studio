"""
도메인 모델 정의.

설계 원칙: 화면(폼/편집기)과 채팅은 동일한 이 모델들을 통해서만 데이터를 읽고 쓴다.
채팅 전용 상태를 별도로 두지 않는다.

Phase 1 범위: BookProject / BookConfig / BookOutline / BookUnit 의
CRUD + 관계 + 자동 재계산 로직까지 구현.
나머지 7종(SourceDocument ~ ExportJob)은 스키마만 먼저 확정해두고
Phase 2 이후에 API/Agent 연동을 붙인다.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, JSON, Relationship, SQLModel, Column


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. BookProject
# ---------------------------------------------------------------------------
class BookProjectBase(SQLModel):
    workspace_id: str = Field(index=True)
    title: str
    status: str = Field(default="draft_config")
    # draft_config -> outline_review -> writing -> reviewing -> completed -> archived
    persona_id: Optional[str] = Field(default=None, index=True)


class BookProject(BookProjectBase, table=True):
    __tablename__ = "book_projects"

    book_id: str = Field(default_factory=lambda: new_id("book"), primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    config: Optional["BookConfig"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    outline: Optional["BookOutline"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )


class BookProjectCreate(SQLModel):
    workspace_id: str
    title: str
    persona_id: Optional[str] = None


class BookProjectRead(BookProjectBase):
    book_id: str
    created_at: datetime
    updated_at: datetime


class BookProjectUpdate(SQLModel):
    title: Optional[str] = None
    status: Optional[str] = None
    persona_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 2. BookConfig
# ---------------------------------------------------------------------------
class BookConfigBase(SQLModel):
    document_type: str = Field(default="general")
    target_reader: str = Field(default="")
    purpose: str = Field(default="")
    tone: str = Field(default="")
    expertise_level: str = Field(default="intermediate")
    chapter_count: int = Field(default=0)
    default_chars_per_chapter: int = Field(default=5000)
    # 총 목표 분량은 사용자가 임의로 못 바꾸게 하고 outline의 unit 합계로만 갱신한다.
    total_target_characters: int = Field(default=0)
    citation_policy: str = Field(default="source_required")
    visual_density: str = Field(default="medium")  # low | medium | high
    output_formats: list[str] = Field(default_factory=lambda: ["pdf"], sa_column=Column(JSON))
    approval_mode: str = Field(default="balanced")  # safe | balanced | auto
    version: int = Field(default=1)


class BookConfig(BookConfigBase, table=True):
    __tablename__ = "book_configs"

    config_id: str = Field(default_factory=lambda: new_id("cfg"), primary_key=True)
    book_id: str = Field(foreign_key="book_projects.book_id", unique=True, index=True)
    updated_at: datetime = Field(default_factory=utcnow)

    book: Optional[BookProject] = Relationship(back_populates="config")


class BookConfigUpdate(SQLModel):
    document_type: Optional[str] = None
    target_reader: Optional[str] = None
    purpose: Optional[str] = None
    tone: Optional[str] = None
    expertise_level: Optional[str] = None
    default_chars_per_chapter: Optional[int] = None
    citation_policy: Optional[str] = None
    visual_density: Optional[str] = None
    output_formats: Optional[list[str]] = None
    approval_mode: Optional[str] = None
    # chapter_count, total_target_characters 는 outline 변경을 통해서만 바뀐다 (직접 PATCH 금지)


# ---------------------------------------------------------------------------
# 3. BookOutline
# ---------------------------------------------------------------------------
class BookOutlineBase(SQLModel):
    status: str = Field(default="draft")  # draft | edited | approved
    version: int = Field(default=1)


class BookOutline(BookOutlineBase, table=True):
    __tablename__ = "book_outlines"

    outline_id: str = Field(default_factory=lambda: new_id("outline"), primary_key=True)
    book_id: str = Field(foreign_key="book_projects.book_id", unique=True, index=True)
    updated_at: datetime = Field(default_factory=utcnow)

    book: Optional[BookProject] = Relationship(back_populates="outline")
    units: list["BookUnit"] = Relationship(
        back_populates="outline",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "BookUnit.order"},
    )


# ---------------------------------------------------------------------------
# 4. BookUnit  (목차/챕터 노드)
# ---------------------------------------------------------------------------
class BookUnitBase(SQLModel):
    parent_id: Optional[str] = Field(default=None, foreign_key="book_units.unit_id")
    order: int = Field(default=0)
    title: str
    description: str = Field(default="")
    target_characters: int = Field(default=5000)
    persona_id: Optional[str] = Field(default=None)  # null이면 book.persona_id 상속
    source_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    must_cover: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="draft")
    # draft -> edited -> approved -> generating -> generated -> reviewed -> finalized
    custom_instructions: Optional[str] = Field(default=None)
    body_md: Optional[str] = Field(default=None)
    body_version: int = Field(default=0)


class BookUnit(BookUnitBase, table=True):
    __tablename__ = "book_units"

    unit_id: str = Field(default_factory=lambda: new_id("unit"), primary_key=True)
    outline_id: str = Field(foreign_key="book_outlines.outline_id", index=True)
    updated_at: datetime = Field(default_factory=utcnow)

    outline: Optional[BookOutline] = Relationship(back_populates="units")


class BookUnitCreate(SQLModel):
    parent_id: Optional[str] = None
    order: Optional[int] = None
    title: str
    description: str = ""
    target_characters: int = 5000
    persona_id: Optional[str] = None
    source_ids: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)
    custom_instructions: Optional[str] = None


class BookUnitUpdate(SQLModel):
    parent_id: Optional[str] = None
    order: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    target_characters: Optional[int] = None
    persona_id: Optional[str] = None
    source_ids: Optional[list[str]] = None
    must_cover: Optional[list[str]] = None
    status: Optional[str] = None
    custom_instructions: Optional[str] = None


class ReorderRequest(SQLModel):
    ordered_unit_ids: list[str]


class BookUnitRead(BookUnitBase):
    unit_id: str
    outline_id: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# 5~11. Phase 2 이후 API 연동 예정 — 스키마만 우선 확정
# ---------------------------------------------------------------------------
class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_documents"

    source_id: str = Field(default_factory=lambda: new_id("source"), primary_key=True)
    workspace_id: str = Field(index=True)
    book_id: Optional[str] = Field(default=None, foreign_key="book_projects.book_id")
    source_type: str  # pdf, docx, hwp, hwpx, xlsx, csv, md, txt, url
    title: str
    content_hash: Optional[str] = Field(default=None, index=True)
    file_path: Optional[str] = None
    url: Optional[str] = None
    raw_text: Optional[str] = None
    sections: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    tables: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="uploaded")  # uploaded | analyzing | analyzed | failed
    created_at: datetime = Field(default_factory=utcnow)


class SourceProfile(SQLModel, table=True):
    __tablename__ = "source_profiles"

    profile_id: str = Field(default_factory=lambda: new_id("profile"), primary_key=True)
    source_id: str = Field(foreign_key="source_documents.source_id", index=True)
    summary: str = Field(default="")
    main_topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    key_findings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tables: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    limitations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    recommended_uses: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    analysis_purpose: Optional[str] = Field(default=None)


class Persona(SQLModel, table=True):
    __tablename__ = "personas"

    persona_id: str = Field(default_factory=lambda: new_id("persona"), primary_key=True)
    scope: str = Field(default="custom")  # system | custom
    name: str
    base_persona_id: Optional[str] = Field(default=None)
    files: dict = Field(default_factory=dict, sa_column=Column(JSON))  # {"PERSONA.md": path, ...}
    defaults: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: Optional[str] = Field(default=None)


class VisualRequest(SQLModel, table=True):
    __tablename__ = "visual_requests"

    visual_id: str = Field(default_factory=lambda: new_id("visual"), primary_key=True)
    unit_id: str = Field(foreign_key="book_units.unit_id", index=True)
    visual_type: str  # table, bar_chart, line_chart, scatter, diagram, illustration, cover
    purpose: str = Field(default="")
    source_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    data_reference: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    caption: str = Field(default="")
    required: bool = Field(default=False)
    status: str = Field(default="planned")
    artifact_id: Optional[str] = Field(default=None)


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    artifact_id: str = Field(default_factory=lambda: new_id("artifact"), primary_key=True)
    type: str  # chart, table, text, image, pdf, docx
    created_by: str
    unit_id: Optional[str] = Field(default=None, foreign_key="book_units.unit_id")
    source_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    file_path: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class BookVersion(SQLModel, table=True):
    __tablename__ = "book_versions"

    version_id: str = Field(default_factory=lambda: new_id("ver"), primary_key=True)
    book_id: str = Field(foreign_key="book_projects.book_id", index=True)
    snapshot_type: str  # config | outline | unit | full
    target_id: str
    diff: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    created_by: str = Field(default="user")  # user | ai
    label: Optional[str] = Field(default=None)


class ExportJob(SQLModel, table=True):
    __tablename__ = "export_jobs"

    export_id: str = Field(default_factory=lambda: new_id("export"), primary_key=True)
    book_id: str = Field(foreign_key="book_projects.book_id", index=True)
    format: str  # pdf | docx | markdown
    options: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="queued")
    result_path: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class ActionPlan(SQLModel, table=True):
    """채팅에서 만들어지는 승인 대기 작업.

    핵심: patch/target_id 는 기존 API(update_config, update_unit 등)가
    받는 것과 동일한 형태로 저장한다 — 승인 시 그 API 함수를 그대로 호출한다.
    """

    __tablename__ = "action_plans"

    action_id: str = Field(default_factory=lambda: new_id("action"), primary_key=True)
    book_id: str = Field(foreign_key="book_projects.book_id", index=True)
    action: str  # ask | edit_config | edit_unit | generate_outline | approve_outline | generate_chapter
    target_type: str  # BookConfig | BookUnit | BookOutline
    target_id: str
    patch: dict = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str = Field(default="")
    status: str = Field(default="pending")  # pending | approved | rejected | applied | failed
    created_at: datetime = Field(default_factory=utcnow)