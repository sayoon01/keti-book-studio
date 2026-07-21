from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    """도메인 객체용 문자열 ID를 생성합니다."""
    return f"{prefix}-{uuid4().hex}"


def utc_now() -> datetime:
    """UTC timezone-aware datetime을 반환합니다."""
    return datetime.now(timezone.utc)


def json_dumps(value: Any) -> str:
    """한글을 보존하며 JSON 문자열로 변환합니다."""
    return json.dumps(value, ensure_ascii=False, default=str)


def json_loads(
    value: str | None,
    default: Any,
) -> Any:
    """빈 값이나 잘못된 JSON을 안전하게 처리합니다."""
    if not value:
        return default

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default