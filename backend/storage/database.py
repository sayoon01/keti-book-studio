from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_env_db = os.environ.get("KETI_DB_PATH")

DATABASE_PATH = (
    Path(_env_db)
    if _env_db
    else PROJECT_ROOT / "keti_book_studio.db"
)

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)


def import_all_models() -> None:
    """
    SQLModel.metadata에 모든 Table 모델을 등록합니다.

    SQLModel.metadata.create_all()은 import되어 등록된
    모델만 테이블로 생성하므로, create_all 전에 반드시
    모든 모델 모듈을 import해야 합니다.
    """

    from backend.storage import (
        models,
        models_publishing,
        models_sources,
    )

    _ = (
        models,
        models_publishing,
        models_sources,
    )


def init_db() -> None:
    """
    운영 SQLite DB에 누락된 테이블을 생성합니다.

    기존 테이블이나 데이터는 삭제하지 않습니다.
    """

    import_all_models()

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
