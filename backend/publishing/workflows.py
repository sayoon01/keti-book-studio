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
    plan_key = f"{unit_id}:plan"
    research_key = f"{unit_id}:research"
    write_key = f"{unit_id}:write"
    review_key = f"{unit_id}:review"
    edit_key = f"{unit_id}:edit"
    revise_key = f"{unit_id}:revise"
    reader_key = f"{unit_id}:reader"
    finalize_key = f"{unit_id}:finalize"

    return [
        ProductionStageDefinition(
            stage_key=plan_key,
            stage_type=ProductionStageType.CHAPTER_PLANNING,
            order_index=10,
            unit_id=unit_id,
            depends_on=[],
        ),
        ProductionStageDefinition(
            stage_key=research_key,
            stage_type=ProductionStageType.CHAPTER_RESEARCH,
            order_index=20,
            unit_id=unit_id,
            depends_on=[
                plan_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=write_key,
            stage_type=ProductionStageType.CHAPTER_WRITING,
            order_index=30,
            unit_id=unit_id,
            depends_on=[
                plan_key,
                research_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=review_key,
            stage_type=ProductionStageType.CHAPTER_REVIEW,
            order_index=40,
            unit_id=unit_id,
            depends_on=[
                plan_key,
                research_key,
                write_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=edit_key,
            stage_type=ProductionStageType.CHAPTER_EDITING,
            order_index=50,
            unit_id=unit_id,
            depends_on=[
                write_key,
                review_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=revise_key,
            stage_type=ProductionStageType.CHAPTER_REVISION,
            order_index=60,
            unit_id=unit_id,
            depends_on=[
                write_key,
                review_key,
                edit_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=reader_key,
            stage_type=(
                ProductionStageType.CHAPTER_READER_TEST
            ),
            order_index=70,
            unit_id=unit_id,
            depends_on=[
                revise_key,
            ],
        ),
        ProductionStageDefinition(
            stage_key=finalize_key,
            stage_type=(
                ProductionStageType.CHAPTER_FINALIZATION
            ),
            order_index=80,
            unit_id=unit_id,
            depends_on=[
                revise_key,
                reader_key,
            ],
        ),
    ]
