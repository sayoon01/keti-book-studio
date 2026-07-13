"""SQLite 엔진 및 세션 설정.

Phase 1은 SQLite 단일 파일로 시작한다. 나중에 Postgres로 옮길 때도
SQLModel/SQLAlchemy 레이어를 쓰고 있으므로 모델 코드는 거의 안 바뀐다.
"""

import os
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.environ.get("KETI_DB_PATH", "keti_book_studio.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite + FastAPI(멀티스레드)에서는 check_same_thread=False 필요
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    # storage.models 를 import 해야 테이블 메타데이터가 등록된다.
    from backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session