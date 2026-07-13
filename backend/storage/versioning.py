"""BookVersion 로깅 공용 헬퍼.

폼 경로와 채팅 경로가 결국 같은 API 함수(update_config, update_unit 등)를
호출하므로, 이 함수를 그 API 함수들 안에 넣어두면 출처와 무관하게
동일한 버전 이력에 자동으로 남는다.
"""

from sqlmodel import Session

from backend.storage.models import BookVersion


def log_version(
    session: Session,
    book_id: str,
    snapshot_type: str,
    target_id: str,
    diff: dict,
    *,
    label: str = "",
    created_by: str = "user",
) -> None:
    version = BookVersion(
        book_id=book_id,
        snapshot_type=snapshot_type,
        target_id=target_id,
        diff=diff,
        label=label,
        created_by=created_by,
    )
    session.add(version)
    session.commit()
