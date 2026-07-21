from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile


CHUNK_SIZE = 1024 * 1024


async def save_upload_file(
    upload: UploadFile,
    destination: Path,
    *,
    max_bytes: int,
) -> tuple[int, str]:
    """
    UploadFile을 chunk 단위로 저장하며 크기와 SHA-256을 계산합니다.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    sha256 = hashlib.sha256()
    total_bytes = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > max_bytes:
                    raise ValueError(
                        f"파일 크기가 제한을 초과했습니다: "
                        f"{max_bytes:,} bytes"
                    )

                sha256.update(chunk)
                output.write(chunk)

        return total_bytes, sha256.hexdigest()

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    finally:
        await upload.close()
