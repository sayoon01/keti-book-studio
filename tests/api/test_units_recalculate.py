"""Phase 1 완료 조건 테스트."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from backend.main import app  # noqa: E402
from backend.storage.database import engine  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    from backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book(client) -> dict:
    resp = client.post(
        "/api/books",
        json={"workspace_id": "ws-1", "title": "ALD 공정 기술서"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_book_creation_auto_creates_empty_config_and_outline(client):
    book = _create_book(client)

    config_resp = client.get(f"/api/books/{book['book_id']}/config")
    assert config_resp.status_code == 200
    assert config_resp.json()["total_target_characters"] == 0

    outline_resp = client.get(f"/api/books/{book['book_id']}/outline")
    assert outline_resp.status_code == 200
    assert outline_resp.json()["units"] == []


def test_unit_target_characters_recalculates_config_total(client):
    book = _create_book(client)
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]

    unit_ids = []
    for i, chars in enumerate([5000, 7000, 6000], start=1):
        resp = client.post(
            f"/api/outlines/{outline['outline_id']}/units",
            json={"title": f"{i}장", "target_characters": chars},
        )
        assert resp.status_code == 200, resp.text
        unit_ids.append(resp.json()["unit_id"])

    config = client.get(f"/api/books/{book['book_id']}/config").json()
    assert config["total_target_characters"] == 5000 + 7000 + 6000
    assert config["chapter_count"] == 3

    third_unit_id = unit_ids[2]
    patch_resp = client.patch(
        f"/api/outlines/{outline['outline_id']}/units/{third_unit_id}",
        json={"target_characters": 9000},
    )
    assert patch_resp.status_code == 200

    config_after = client.get(f"/api/books/{book['book_id']}/config").json()
    assert config_after["total_target_characters"] == 5000 + 7000 + 9000


def test_unit_delete_recalculates_total(client):
    book = _create_book(client)
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]

    ids = []
    for chars in [4000, 4000]:
        resp = client.post(
            f"/api/outlines/{outline['outline_id']}/units",
            json={"title": "장", "target_characters": chars},
        )
        ids.append(resp.json()["unit_id"])

    client.delete(f"/api/outlines/{outline['outline_id']}/units/{ids[0]}")

    config = client.get(f"/api/books/{book['book_id']}/config").json()
    assert config["total_target_characters"] == 4000
    assert config["chapter_count"] == 1


def test_cannot_patch_total_characters_directly(client):
    book = _create_book(client)

    resp = client.patch(
        f"/api/books/{book['book_id']}/config",
        json={"total_target_characters": 999999, "tone": "전문적"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_target_characters"] == 0
    assert body["tone"] == "전문적"


def test_approve_outline_requires_at_least_one_unit(client):
    book = _create_book(client)

    resp = client.post(f"/api/books/{book['book_id']}/outline/approve")
    assert resp.status_code == 400


def test_editing_approved_outline_reverts_to_edited(client):
    book = _create_book(client)
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]

    create_resp = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장", "target_characters": 3000},
    )
    unit_id = create_resp.json()["unit_id"]

    approve_resp = client.post(f"/api/books/{book['book_id']}/outline/approve")
    assert approve_resp.json()["status"] == "approved"

    client.patch(
        f"/api/outlines/{outline['outline_id']}/units/{unit_id}",
        json={"title": "1장 (수정됨)"},
    )

    outline_after = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    assert outline_after["status"] == "edited"
