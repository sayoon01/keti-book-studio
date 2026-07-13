"""outline/unit 변경 시 공용으로 필요한 재계산·검증 로직."""

from sqlmodel import Session, select

from backend.storage.models import BookConfig, BookOutline, BookUnit


def recalc_config_from_outline(session: Session, book_id: str) -> BookConfig | None:
    config = session.exec(select(BookConfig).where(BookConfig.book_id == book_id)).first()
    outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()
    if not config or not outline:
        return config

    units = session.exec(select(BookUnit).where(BookUnit.outline_id == outline.outline_id)).all()

    config.total_target_characters = sum(u.target_characters for u in units)
    config.chapter_count = len([u for u in units if u.parent_id is None])
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def assert_outline_editable(outline: BookOutline) -> None:
    if outline.status == "approved":
        outline.status = "edited"
