from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# 중요:
# create_all() 전에 모든 SQLModel table 모델이 import되어야 합니다.
from backend.storage import models  # noqa: F401
from backend.storage import models_publishing  # noqa: F401
from backend.storage import models_sources  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_env_db = os.environ.get("KETI_DB_PATH")
DATABASE_PATH = (
    Path(_env_db) if _env_db else PROJECT_ROOT / "keti_book_studio.db"
)

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
