"""자료 라이브러리 디렉터리 업로드 API 테스트."""

import os
import tempfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()

from backend.main import app  # noqa: E402
from backend.storage.database import engine  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db(monkeypatch, tmp_path):
    from backend import settings

    monkeypatch.setattr(settings, "SOURCE_LIBRARY_DIR", tmp_path / "source_library")

    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book(client) -> dict:
    resp = client.post(
        "/api/books",
        json={"workspace_id": "ws-1", "title": "테스트 책"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_upload_directory(client):
    response = client.post(
        "/api/source-library/collections/directory",
        data={
            "relative_paths": [
                "ADK자료/공식문서/agent.md",
                "ADK자료/실습코드/example.py",
            ],
            "collection_name": "ADK 자료",
            "root_name": "ADK자료",
        },
        files=[
            (
                "files",
                (
                    "agent.md",
                    BytesIO(b"# Agent"),
                    "text/markdown",
                ),
            ),
            (
                "files",
                (
                    "example.py",
                    BytesIO(b"print('hello')"),
                    "text/x-python",
                ),
            ),
        ],
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["collection"]["name"] == "ADK 자료"
    assert body["uploaded_files"] == 2
    assert body["failed_files"] == 0


def test_collection_tree(client):
    upload_response = client.post(
        "/api/source-library/collections/directory",
        data={
            "relative_paths": [
                "Root/docs/a.md",
                "Root/code/b.py",
            ],
            "collection_name": "Root",
            "root_name": "Root",
        },
        files=[
            (
                "files",
                ("a.md", BytesIO(b"A"), "text/markdown"),
            ),
            (
                "files",
                ("b.py", BytesIO(b"B"), "text/x-python"),
            ),
        ],
    )

    assert upload_response.status_code == 201, upload_response.text
    collection_id = upload_response.json()["collection"]["id"]

    response = client.get(
        f"/api/source-library/collections/{collection_id}/tree"
    )

    assert response.status_code == 200

    tree = response.json()
    assert tree["collection"]["id"] == collection_id
    assert len(tree["roots"]) >= 1


def test_link_collection_to_book(client):
    book = _create_book(client)

    upload_response = client.post(
        "/api/source-library/collections/directory",
        data={
            "relative_paths": ["Docs/note.md"],
            "collection_name": "Docs",
            "root_name": "Docs",
            "book_id": book["book_id"],
        },
        files=[
            (
                "files",
                ("note.md", BytesIO(b"hello"), "text/markdown"),
            ),
        ],
    )
    assert upload_response.status_code == 201, upload_response.text

    collection_id = upload_response.json()["collection"]["id"]

    links = client.get(
        f"/api/source-library/books/{book['book_id']}/collections"
    )
    assert links.status_code == 200
    body = links.json()
    assert len(body) == 1
    assert body[0]["collection_id"] == collection_id
