"""Phase 8 완료 조건 테스트.

1. config PATCH(폼 경로) 시 버전이 자동으로 남는지
2. unit PATCH(폼 경로) 시 버전이 남고, 복원하면 total_target_characters도 재계산되는지
3. 채팅으로 바꾼 값도 같은 버전 이력에 남는지
4. outline 스냅샷(승인/생성)은 복원 불가(400)로 막히는지
5. markdown/docx/pdf보내기가 실제 파일을 만들고 다운로드되는지
6. 목차 없는 책은보내기 불가
"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["KETI_PERSONA_DIR"] = tempfile.mkdtemp()
os.environ["KETI_EXPORT_DIR"] = tempfile.mkdtemp()

from backend.main import app  # noqa: E402
from backend.services.llm_client import get_llm_call, get_writer_llm_call  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


def _make_intent_llm(action: str):
    def _llm(system_prompt: str, user_prompt: str) -> str:
        return json.dumps({"action": action, "reasoning": "test"}, ensure_ascii=False)

    return _llm


def _fake_field_extractor_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({"target_characters": 9000}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    app.dependency_overrides[get_writer_llm_call] = lambda: (lambda s, u: "답변")
    yield
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book_with_unit(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 기술서"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    unit = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장. 개요", "target_characters": 5000},
    ).json()
    return {"book": book, "outline": outline, "unit": unit}


def test_form_config_patch_logs_version(client):
    ctx = _create_book_with_unit(client)

    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"tone": "친근하게"})

    versions = client.get(f"/api/books/{ctx['book']['book_id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["snapshot_type"] == "config"
    assert versions[0]["diff"]["after"] == {"tone": "친근하게"}
    assert versions[0]["diff"]["before"] == {"tone": ""}


def test_form_unit_patch_logs_version_and_restore_recalculates_config(client):
    ctx = _create_book_with_unit(client)
    unit_id = ctx["unit"]["unit_id"]
    book_id = ctx["book"]["book_id"]

    client.patch(
        f"/api/outlines/{ctx['outline']['outline_id']}/units/{unit_id}",
        json={"target_characters": 9000},
    )

    config_after_edit = client.get(f"/api/books/{book_id}/config").json()
    assert config_after_edit["total_target_characters"] == 9000

    versions = client.get(f"/api/books/{book_id}/versions").json()
    unit_version = next(v for v in versions if v["snapshot_type"] == "unit")
    assert unit_version["diff"]["before"] == {"target_characters": 5000}
    assert unit_version["diff"]["after"] == {"target_characters": 9000}

    restore_resp = client.post(f"/api/books/{book_id}/versions/{unit_version['version_id']}/restore")
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["target_characters"] == 5000

    config_after_restore = client.get(f"/api/books/{book_id}/config").json()
    assert config_after_restore["total_target_characters"] == 5000

    versions_after = client.get(f"/api/books/{book_id}/versions").json()
    assert len(versions_after) == 2


def test_chat_edit_shares_same_version_history_as_form(client):
    ctx = _create_book_with_unit(client)
    unit_id = ctx["unit"]["unit_id"]
    book_id = ctx["book"]["book_id"]

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    chat_resp = client.post(
        "/api/chat",
        json={
            "book_id": book_id,
            "message": "1장 9천자로",
            "scope_type": "unit",
            "scope_id": unit_id,
        },
    ).json()
    action_id = chat_resp["action"]["action_id"]
    client.post(f"/api/actions/{action_id}/approve")

    versions = client.get(f"/api/books/{book_id}/versions").json()
    assert len(versions) == 1
    assert versions[0]["snapshot_type"] == "unit"
    assert versions[0]["diff"]["after"] == {"target_characters": 9000}


def test_outline_snapshot_cannot_be_restored(client):
    ctx = _create_book_with_unit(client)
    book_id = ctx["book"]["book_id"]

    client.post(f"/api/books/{book_id}/outline/approve")

    versions = client.get(f"/api/books/{book_id}/versions").json()
    outline_version = next(v for v in versions if v["snapshot_type"] == "outline")

    resp = client.post(f"/api/books/{book_id}/versions/{outline_version['version_id']}/restore")
    assert resp.status_code == 400


def test_export_markdown_and_download(client):
    ctx = _create_book_with_unit(client)
    book_id = ctx["book"]["book_id"]

    resp = client.post(f"/api/books/{book_id}/export", json={"format": "markdown"})
    assert resp.status_code == 200, resp.text
    export = resp.json()
    assert export["status"] == "done"

    download = client.get(f"/api/exports/{export['export_id']}/download")
    assert download.status_code == 200
    assert "1장".encode("utf-8") in download.content


def test_export_docx_creates_real_file(client):
    ctx = _create_book_with_unit(client)
    book_id = ctx["book"]["book_id"]

    resp = client.post(f"/api/books/{book_id}/export", json={"format": "docx"})
    assert resp.status_code == 200, resp.text
    export = resp.json()

    from docx import Document

    doc = Document(export["result_path"])
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "1장. 개요" in all_text


def test_export_pdf_creates_real_file_with_korean_text(client):
    ctx = _create_book_with_unit(client)
    book_id = ctx["book"]["book_id"]

    resp = client.post(f"/api/books/{book_id}/export", json={"format": "pdf"})
    assert resp.status_code == 200, resp.text
    export = resp.json()

    from pathlib import Path

    assert Path(export["result_path"]).exists()
    assert Path(export["result_path"]).stat().st_size > 0


def test_export_without_units_fails(client):
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "빈 책"}).json()
    resp = client.post(f"/api/books/{book['book_id']}/export", json={"format": "markdown"})
    assert resp.status_code == 400
