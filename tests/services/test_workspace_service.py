"""WorkspaceService 테스트."""

import os
import tempfile

import pytest
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from backend.services.workspace_service import WorkspaceService  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.models import (  # noqa: E402
    BookConfig,
    BookOutline,
    BookProject,
    BookUnit,
    SourceDocument,
    SourceProfile,
)
from backend.storage.models_sources import (  # noqa: E402
    BookSourceCollection,
    SourceCollection,
    SourceNode,
)


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def _seed_book_with_sources(session: Session) -> tuple[str, str, str]:
    book = BookProject(
        workspace_id="ws-1",
        title="테스트 책",
    )
    session.add(book)
    session.commit()
    session.refresh(book)

    config = BookConfig(book_id=book.book_id)
    session.add(config)

    outline = BookOutline(book_id=book.book_id)
    session.add(outline)
    session.commit()
    session.refresh(outline)

    unit = BookUnit(
        outline_id=outline.outline_id,
        title="1장",
        order=1,
    )
    session.add(unit)

    collection = SourceCollection(
        name="자료",
        collection_type="DIRECTORY_UPLOAD",
        status="READY",
        storage_path="/tmp/unused",
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)

    document = SourceDocument(
        workspace_id="ws-1",
        book_id=book.book_id,
        source_type="md",
        title="readme",
        raw_text="# Hello",
        status="analyzed",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    profile = SourceProfile(
        source_id=document.source_id,
        summary="Hello summary",
        main_topics=["hello", "test"],
    )
    session.add(profile)

    node = SourceNode(
        collection_id=collection.id,
        node_type="FILE",
        name="readme.md",
        relative_path="readme.md",
        depth=0,
        document_id=document.source_id,
        status="READY",
    )
    session.add(node)

    link = BookSourceCollection(
        book_id=book.book_id,
        collection_id=collection.id,
        linked_by="USER",
    )
    session.add(link)
    session.commit()
    session.refresh(unit)

    return book.book_id, unit.unit_id, document.source_id


def test_build_workspace_from_book_collections():
    with Session(engine) as session:
        book_id, _, source_id = _seed_book_with_sources(session)

        service = WorkspaceService(session)
        workspace = service.build_workspace(
            book_id=book_id,
        )

    assert workspace.book.book_id == book_id
    assert workspace.book.title == "테스트 책"
    assert len(workspace.sources) == 1
    assert workspace.sources[0].source_id == source_id
    assert workspace.sources[0].summary == "Hello summary"
    assert workspace.sources[0].keywords == ["hello", "test"]


def test_build_workspace_with_unit():
    with Session(engine) as session:
        book_id, unit_id, _ = _seed_book_with_sources(session)

        service = WorkspaceService(session)
        workspace = service.build_workspace(
            book_id=book_id,
            unit_id=unit_id,
        )

    assert workspace.unit is not None
    assert workspace.unit.unit_id == unit_id
    assert workspace.unit.title == "1장"
    assert workspace.unit.order_index == 1


def test_build_workspace_book_not_found():
    with Session(engine) as session:
        service = WorkspaceService(session)

        with pytest.raises(ValueError, match="BookProject"):
            service.build_workspace(book_id="book-missing")
