from __future__ import annotations

from backend.publishing.enums import (
    ProductionStageType,
)
from backend.publishing.production_schemas import (
    ProductionStageDefinition,
)


def build_chapter_workflow(
    *,
    unit_id: str,
) -> list[ProductionStageDefinition]:
    return [
        ProductionStageDefinition(
            stage_key=f"{unit_id}:plan",
            stage_type=(
                ProductionStageType.CHAPTER_PLANNING
            ),
            order_index=10,
            unit_id=unit_id,
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:research",
            stage_type=(
                ProductionStageType.CHAPTER_RESEARCH
            ),
            order_index=20,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:plan",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:write",
            stage_type=(
                ProductionStageType.CHAPTER_WRITING
            ),
            order_index=30,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:research",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:review",
            stage_type=(
                ProductionStageType.CHAPTER_REVIEW
            ),
            order_index=40,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:write",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:edit",
            stage_type=(
                ProductionStageType.CHAPTER_EDITING
            ),
            order_index=50,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:review",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:revise",
            stage_type=(
                ProductionStageType.CHAPTER_REVISION
            ),
            order_index=60,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:edit",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:reader",
            stage_type=(
                ProductionStageType
                .CHAPTER_READER_TEST
            ),
            order_index=70,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:revise",
            ],
        ),
        ProductionStageDefinition(
            stage_key=f"{unit_id}:finalize",
            stage_type=(
                ProductionStageType
                .CHAPTER_FINALIZATION
            ),
            order_index=80,
            unit_id=unit_id,
            depends_on=[
                f"{unit_id}:reader",
            ],
        ),
    ]
