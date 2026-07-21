from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReaderPolicyContext:
    is_important_unit: bool
    is_final_review: bool
    automation_level: str = "BALANCED"


def should_run_reader_test(
    context: ReaderPolicyContext,
) -> bool:
    if context.automation_level == "MANUAL":
        return (
            context.is_important_unit
            or context.is_final_review
        )

    if context.automation_level == "BALANCED":
        return (
            context.is_important_unit
            or context.is_final_review
        )

    if context.automation_level == "AUTONOMOUS":
        return (
            context.is_important_unit
            or context.is_final_review
        )

    return False
