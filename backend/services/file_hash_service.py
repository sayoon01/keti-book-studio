from __future__ import annotations

import hashlib
from pathlib import Path


class FileHashService:
    """파일 중복 확인을 위한 SHA-256 계산."""

    @staticmethod
    def calculate_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def calculate_file(
        file_path: str | Path,
        chunk_size: int = 1024 * 1024,
    ) -> str:
        path = Path(file_path)

        digest = hashlib.sha256()

        with path.open("rb") as file:
            while chunk := file.read(chunk_size):
                digest.update(chunk)

        return digest.hexdigest()