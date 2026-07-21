from __future__ import annotations

from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    pass


def normalize_relative_path(raw_path: str) -> str:
    """
    브라우저의 webkitRelativePath를 안전한 POSIX 상대 경로로 정규화합니다.
    """
    value = raw_path.replace("\\", "/").strip()

    if not value:
        raise UnsafePathError("빈 상대 경로는 허용되지 않습니다.")

    path = PurePosixPath(value)

    if path.is_absolute():
        raise UnsafePathError("절대 경로는 허용되지 않습니다.")

    if any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafePathError(
            f"안전하지 않은 상대 경로입니다: {raw_path}"
        )

    return path.as_posix()


def safe_join(root: Path, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path)
    root_resolved = root.resolve()
    destination = (root / normalized).resolve()

    try:
        destination.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError(
            f"저장 경로가 루트를 벗어났습니다: {relative_path}"
        ) from exc

    return destination
