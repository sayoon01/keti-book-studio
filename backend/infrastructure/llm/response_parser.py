from __future__ import annotations

import json
import re
from typing import Any

from backend.infrastructure.llm.exceptions import (
    OllamaLowQualityResponseError,
    OllamaResponseParseError,
)


def parse_json_object(
    text: str,
) -> dict[str, Any]:
    cleaned = strip_code_fence(text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OllamaResponseParseError(
            f"JSON 파싱에 실패했습니다: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise OllamaResponseParseError(
            "JSON 최상위 값은 객체여야 합니다."
        )

    return parsed


def clean_markdown(
    text: str,
) -> str:
    stripped = text.strip()

    pattern = re.compile(
        r"^```(?:markdown|md)\s*\n(.*)\n```$",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.match(stripped)

    if match:
        return match.group(1).strip()

    return stripped


def validate_text_quality(
    text: str,
    *,
    minimum_length: int,
) -> None:
    if len(text) < minimum_length:
        raise OllamaLowQualityResponseError(
            "응답이 너무 짧습니다. "
            f"length={len(text)}, "
            f"minimum={minimum_length}"
        )

    repeated_pattern = re.compile(
        r"(.{10,50})\1{4,}",
        re.DOTALL,
    )

    if repeated_pattern.search(text):
        raise OllamaLowQualityResponseError(
            "응답에서 비정상 반복이 감지되었습니다."
        )


def strip_code_fence(
    text: str,
) -> str:
    stripped = text.strip()

    pattern = re.compile(
        r"^```(?:json)?\s*(.*?)\s*```$",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.match(stripped)

    if match:
        return match.group(1).strip()

    return stripped
