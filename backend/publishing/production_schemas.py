from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.publishing.enums import ProductionStageType


class CreateProductionRunRequest(BaseModel):
    book_id: str
    workspace_id: str

    workflow_type: str = "technical_book"
    automation_level: str = "BALANCED"

    requested_by: str | None = None

    input_data: dict[str, Any] = Field(
        default_factory=dict
    )


class ProductionStageDefinition(BaseModel):
    stage_key: str
    stage_type: ProductionStageType

    order_index: int

    unit_id: str | None = None

    depends_on: list[str] = Field(
        default_factory=list
    )

    max_retries: int = 1

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class ProductionRunResponse(BaseModel):
    run_id: str
    book_id: str
    workspace_id: str

    workflow_type: str
    automation_level: str

    status: str

    current_stage_id: str | None = None

    total_stages: int
    completed_stages: int
    failed_stages: int

    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProductionStageResponse(BaseModel):
    stage_id: str
    run_id: str

    book_id: str
    unit_id: str | None = None

    stage_key: str
    stage_type: str
    order_index: int

    status: str

    depends_on: list[str]

    retry_count: int
    max_retries: int

    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProductionRunDetailResponse(BaseModel):
    run: ProductionRunResponse
    stages: list[ProductionStageResponse]
