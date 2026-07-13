from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import BookConfig, BookUnit, BookVersion
from backend.storage.recalculation import recalc_config_from_outline
from backend.storage.versioning import log_version

router = APIRouter(prefix="/api/books/{book_id}/versions", tags=["versions"])

RESTORABLE_SNAPSHOT_TYPES = {"config", "unit"}


@router.get("")
def list_versions(book_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(BookVersion)
        .where(BookVersion.book_id == book_id)
        .order_by(BookVersion.created_at.desc())
    ).all()


@router.post("/{version_id}/restore")
def restore_version(book_id: str, version_id: str, session: Session = Depends(get_session)):
    version = session.get(BookVersion, version_id)
    if not version or version.book_id != book_id:
        raise HTTPException(404, "version not found")

    if version.snapshot_type not in RESTORABLE_SNAPSHOT_TYPES:
        raise HTTPException(
            400,
            f"'{version.snapshot_type}' 타입의 버전은 복원을 지원하지 않습니다 "
            f"(config, unit 스냅샷만 복원 가능).",
        )

    before = (version.diff or {}).get("before")
    if before is None:
        raise HTTPException(400, "이 버전에는 복원 가능한 이전 상태 정보가 없습니다.")

    if version.snapshot_type == "config":
        config = session.exec(
            select(BookConfig).where(BookConfig.book_id == book_id)
        ).first()
        if not config:
            raise HTTPException(404, "config not found")

        current_snapshot = {field: getattr(config, field) for field in before}
        for field, value in before.items():
            setattr(config, field, value)
        config.version += 1

        session.add(config)
        session.commit()
        session.refresh(config)

        log_version(
            session, book_id, "config", book_id,
            {"before": current_snapshot, "after": before},
            label=f"버전 복원 ({version_id})",
        )
        session.refresh(config)
        return config

    unit = session.get(BookUnit, version.target_id)
    if not unit:
        raise HTTPException(404, "unit not found")

    current_snapshot = {field: getattr(unit, field) for field in before}
    for field, value in before.items():
        setattr(unit, field, value)

    session.add(unit)
    session.commit()
    session.refresh(unit)

    recalc_config_from_outline(session, book_id)

    log_version(
        session, book_id, "unit", unit.unit_id,
        {"before": current_snapshot, "after": before},
        label=f"버전 복원 ({version_id})",
    )
    session.refresh(unit)
    return unit
