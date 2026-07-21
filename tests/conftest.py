from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.main import app
from backend.storage.database import get_session

from backend.storage import models  # noqa: F401
from backend.storage import models_publishing  # noqa: F401
from backend.storage import models_sources  # noqa: F401

from backend.storage.models import (
    BookConfig,
    BookOutline,
    BookProject,
    BookUnit,
    SourceDocument,
    SourceProfile,
)
from backend.storage.models_sources import (
    BookSourceCollection,
    SourceCollection,
    SourceNode,
)


@pytest.fixture
def isolated_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    SQLModel.metadata.create_all(engine)

    table_names = inspect(engine).get_table_names()

    assert "production_runs" in table_names
    assert "production_stages" in table_names
    assert "agent_tasks" in table_names
    assert "source_collections" in table_names

    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def isolated_session(
    isolated_engine,
) -> Generator[Session, None, None]:
    with Session(isolated_engine) as session:
        yield session


@pytest.fixture
def test_engine(isolated_engine):
    return isolated_engine


@pytest.fixture
def session(isolated_session) -> Generator[Session, None, None]:
    yield isolated_session


@pytest.fixture
def client(isolated_engine) -> Generator[TestClient, None, None]:
    def override_get_session():
        with Session(isolated_engine) as db_session:
            yield db_session

    app.dependency_overrides[get_session] = (
        override_get_session
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def prepared_book(
    isolated_session: Session,
) -> BookProject:
    book = BookProject(
        workspace_id="workspace-test",
        title="테스트 책",
    )

    isolated_session.add(book)
    isolated_session.commit()
    isolated_session.refresh(book)

    config = BookConfig(book_id=book.book_id)
    isolated_session.add(config)
    isolated_session.commit()

    return book


@pytest.fixture
def prepared_unit(
    isolated_session: Session,
    prepared_book: BookProject,
) -> BookUnit:
    outline = BookOutline(book_id=prepared_book.book_id)

    isolated_session.add(outline)
    isolated_session.commit()
    isolated_session.refresh(outline)

    unit = BookUnit(
        outline_id=outline.outline_id,
        title="1장",
        order=1,
    )

    isolated_session.add(unit)
    isolated_session.commit()
    isolated_session.refresh(unit)

    return unit


@pytest.fixture
def prepared_book_with_source_collection(
    isolated_session: Session,
) -> dict[str, str]:
    book = BookProject(
        workspace_id="ws-1",
        title="테스트 책",
    )
    isolated_session.add(book)
    isolated_session.commit()
    isolated_session.refresh(book)

    config = BookConfig(
        book_id=book.book_id,
        approval_mode="balanced",
    )
    isolated_session.add(config)

    collection = SourceCollection(
        name="자료",
        collection_type="DIRECTORY_UPLOAD",
        status="READY",
        storage_path="/tmp/unused",
    )
    isolated_session.add(collection)
    isolated_session.commit()
    isolated_session.refresh(collection)

    document = SourceDocument(
        workspace_id="ws-1",
        book_id=book.book_id,
        source_type="md",
        title="readme",
        raw_text="# Hello",
        status="analyzed",
    )
    isolated_session.add(document)
    isolated_session.commit()
    isolated_session.refresh(document)

    profile = SourceProfile(
        source_id=document.source_id,
        summary="Hello summary",
        main_topics=["hello", "test"],
    )
    isolated_session.add(profile)

    node = SourceNode(
        collection_id=collection.id,
        node_type="FILE",
        name="readme.md",
        relative_path="readme.md",
        depth=0,
        document_id=document.source_id,
        status="READY",
    )
    isolated_session.add(node)

    link = BookSourceCollection(
        book_id=book.book_id,
        collection_id=collection.id,
        linked_by="USER",
    )
    isolated_session.add(link)
    isolated_session.commit()

    return {
        "book_id": book.book_id,
        "collection_id": collection.id,
        "source_id": document.source_id,
    }
