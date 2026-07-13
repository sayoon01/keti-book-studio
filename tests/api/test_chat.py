"""Phase 7 완료 조건 테스트."""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["KETI_PERSONA_DIR"] = tempfile.mkdtemp()

from backend.main import app  # noqa: E402
from backend.services.llm_client import get_llm_call, get_writer_llm_call  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


def _make_intent_llm(action: str):
    def _llm(system_prompt: str, user_prompt: str) -> str:
        return json.dumps({"action": action, "reasoning": "test"}, ensure_ascii=False)

    return _llm


def _fake_field_extractor_llm(system_prompt: str, user_prompt: str) -> str:
    if "챕터" in system_prompt:
        return json.dumps({"target_characters": 7000}, ensure_ascii=False)
    return json.dumps({"tone": "더 캐주얼하게"}, ensure_ascii=False)


def _fake_qa_llm(system_prompt: str, user_prompt: str) -> str:
    return "이 자료는 ALD 공정의 온도/압력 영향을 다룹니다."


@pytest.fixture(autouse=True)
def _reset_db():
    from backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    app.dependency_overrides[get_writer_llm_call] = lambda: _fake_qa_llm
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


def test_ask_returns_answer_immediately_without_action_plan(client):
    app.dependency_overrides[get_llm_call] = lambda: _make_intent_llm("ask")
    ctx = _create_book_with_unit(client)

    resp = client.post(
        "/api/chat",
        json={"book_id": ctx["book"]["book_id"], "message": "이 책은 무슨 내용이야?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "answered"
    assert "ALD" in body["answer"]


def test_edit_unit_requires_approval_in_default_balanced_mode(client):
    ctx = _create_book_with_unit(client)

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    resp = client.post(
        "/api/chat",
        json={
            "book_id": ctx["book"]["book_id"],
            "message": "1장 글자수를 7천자로 바꿔줘",
            "scope_type": "unit",
            "scope_id": ctx["unit"]["unit_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending_approval"
    assert body["action"]["action"] == "edit_unit"
    assert body["action"]["patch"] == {"target_characters": 7000}

    outline_data = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_data["units"][0]["target_characters"] == 5000


def test_approving_edit_unit_actually_changes_unit_and_recalculates_config(client):
    ctx = _create_book_with_unit(client)

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    chat_resp = client.post(
        "/api/chat",
        json={
            "book_id": ctx["book"]["book_id"],
            "message": "1장 글자수를 7천자로 바꿔줘",
            "scope_type": "unit",
            "scope_id": ctx["unit"]["unit_id"],
        },
    ).json()
    action_id = chat_resp["action"]["action_id"]

    approve_resp = client.post(f"/api/actions/{action_id}/approve")
    assert approve_resp.status_code == 200, approve_resp.text
    approve_body = approve_resp.json()
    assert approve_body["action"]["status"] == "applied"
    # result가 commit 이후 만료되어 빈 dict로 오는 버그 회귀 방지
    assert approve_body["result"]["target_characters"] == 7000
    assert approve_body["result"]["unit_id"] == ctx["unit"]["unit_id"]

    config = client.get(f"/api/books/{ctx['book']['book_id']}/config").json()
    assert config["total_target_characters"] == 7000

    outline_data = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_data["units"][0]["target_characters"] == 7000


def test_rejecting_action_does_not_change_anything(client):
    ctx = _create_book_with_unit(client)

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    chat_resp = client.post(
        "/api/chat",
        json={
            "book_id": ctx["book"]["book_id"],
            "message": "1장 글자수를 7천자로 바꿔줘",
            "scope_type": "unit",
            "scope_id": ctx["unit"]["unit_id"],
        },
    ).json()
    action_id = chat_resp["action"]["action_id"]

    reject_resp = client.post(f"/api/actions/{action_id}/reject")
    assert reject_resp.json()["status"] == "rejected"

    outline_data = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_data["units"][0]["target_characters"] == 5000

    resp = client.post(f"/api/actions/{action_id}/approve")
    assert resp.status_code == 400


def test_auto_mode_executes_edit_immediately(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    resp = client.post(
        "/api/chat",
        json={
            "book_id": ctx["book"]["book_id"],
            "message": "1장 글자수를 7천자로 바꿔줘",
            "scope_type": "unit",
            "scope_id": ctx["unit"]["unit_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "executed"

    outline_data = client.get(f"/api/books/{ctx['book']['book_id']}/outline").json()
    assert outline_data["units"][0]["target_characters"] == 7000


def test_generate_outline_always_requires_approval_even_in_auto_mode(client):
    ctx = _create_book_with_unit(client)
    client.patch(f"/api/books/{ctx['book']['book_id']}/config", json={"approval_mode": "auto"})
    app.dependency_overrides[get_llm_call] = lambda: _make_intent_llm("generate_outline")

    resp = client.post(
        "/api/chat",
        json={"book_id": ctx["book"]["book_id"], "message": "목차 완전히 다시 만들어줘"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending_approval"


def test_edit_unit_without_target_hint_fails(client):
    ctx = _create_book_with_unit(client)

    def dispatch(system_prompt, user_prompt):
        if "챕터(목차 항목)" in system_prompt:
            return _fake_field_extractor_llm(system_prompt, user_prompt)
        return _make_intent_llm("edit_unit")(system_prompt, user_prompt)

    app.dependency_overrides[get_llm_call] = lambda: dispatch

    resp = client.post(
        "/api/chat",
        json={
            "book_id": ctx["book"]["book_id"],
            "message": "글자수를 늘려줘",
        },
    )
    assert resp.status_code == 400
