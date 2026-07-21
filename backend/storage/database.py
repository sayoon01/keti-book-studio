"""SQLite 엔진 및 세션 설정.

Phase 1은 SQLite 단일 파일로 시작한다. 나중에 Postgres로 옮길 때도
SQLModel/SQLAlchemy 레이어를 쓰고 있으므로 모델 코드는 거의 안 바뀐다.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# 테이블 등록을 위한 import
from backend.storage import models  # noqa: F401
from backend.storage import models_publishing  # noqa: F401
from backend.storage import models_sources  # noqa: F401


ROOT_DIR = Path(__file__).resolve().parents[2]
_env_db = os.environ.get("KETI_DB_PATH")
DATABASE_PATH = Path(_env_db) if _env_db else ROOT_DIR / "keti_book_studio.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
    },
)


def init_db() -> None:
    """
    등록된 SQLModel 테이블을 생성한다.

    기존 테이블은 유지하고 존재하지 않는 새 테이블만 생성한다.
    """
    SQLModel.metadata.create_all(engine)


def create_db_and_tables() -> None:
    """기존 호출부(main.py 등) 호환용."""
    init_db()


def get_session():
    with Session(engine) as session:
        yield session
