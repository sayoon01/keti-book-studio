"""Phase 5 완료 조건 테스트."""

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
from backend.services.llm_client import (  # noqa: E402
    get_llm_call,
    get_reviewer_llm_call,
    get_reviser_llm_call,
    get_writer_llm_call,
)
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


def _fake_research_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "summary": "ALD 공정 파라미터 요약",
            "main_topics": ["온도", "압력"],
            "key_findings": ["온도가 반응속도에 영향"],
            "tables": [],
            "limitations": ["정량 검증 데이터 없음"],
            "recommended_uses": ["기술서"],
        },
        ensure_ascii=False,
    )


def _fake_outline_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "chapters": [
                {
                    "title": "1장. ALD 공정 개요",
                    "description": "ALD 공정의 정의와 원리",
                    "target_characters": 3000,
                    "must_cover": ["정의"],
                }
            ]
        },
        ensure_ascii=False,
    )


def _dispatching_llm_call(system_prompt: str, user_prompt: str) -> str:
    if "목차를 설계하는 전문 편집자" in system_prompt:
        return _fake_outline_llm(system_prompt, user_prompt)
    return _fake_research_llm(system_prompt, user_prompt)


CALL_LOG: list[str] = []


def _fake_writer(system_prompt: str, user_prompt: str) -> str:
    CALL_LOG.append("writer")
    return "## ALD 공정 개요\n\nALD 공정은 온도와 압력에 민감하다."


def _make_fake_reviewer(needs_revision: bool):
    def _reviewer(system_prompt: str, user_prompt: str) -> str:
        CALL_LOG.append("reviewer")
        issues = (
            [{"type": "근거 부족", "description": "수치 근거 없음", "location_hint": "온도와 압력에 민감하다"}]
            if needs_revision
            else []
        )
        return json.dumps(
            {"issues": issues, "needs_revision": needs_revision, "overall_comment": "검토 완료"},
            ensure_ascii=False,
        )

    return _reviewer


def _fake_reviser(system_prompt: str, user_prompt: str) -> str:
    CALL_LOG.append("reviser")
    return "## ALD 공정 개요 (수정됨)\n\n온도와 압력이 반응 속도와 균일성에 영향을 준다."


@pytest.fixture(autouse=True)
def _reset_db():
    CALL_LOG.clear()
    from backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    app.dependency_overrides[get_llm_call] = lambda: _dispatching_llm_call
    app.dependency_overrides[get_writer_llm_call] = lambda: _fake_writer
    app.dependency_overrides[get_reviser_llm_call] = lambda: _fake_reviser
    yield
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_approved_book(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 기술서"}).json()
    source = client.post(
        f"/api/books/{book['book_id']}/sources/upload",
        files={"file": ("note.txt", b"ALD process notes about temperature and pressure.", "text/plain")},
    ).json()
    client.post(f"/api/sources/{source['source_id']}/analyze", json={})

    personas = client.get("/api/personas").json()
    tech_expert_id = next(p for p in personas if p["name"] == "기술 전문가")["persona_id"]
    client.patch(f"/api/books/{book['book_id']}", json={"persona_id": tech_expert_id})

    outline_data = client.post(f"/api/books/{book['book_id']}/outline/generate", json={}).json()
    client.post(f"/api/books/{book['book_id']}/outline/approve")

    return {
        "book": book,
        "outline_id": outline_data["outline"]["outline_id"],
        "unit_id": outline_data["units"][0]["unit_id"],
    }


def test_generate_body_without_evidence_fails(client):
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "빈 책"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    unit = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장", "target_characters": 1000},
    ).json()
    client.post(f"/api/books/{book['book_id']}/outline/approve")

    resp = client.post(f"/api/outlines/{outline['outline_id']}/units/{unit['unit_id']}/generate")
    assert resp.status_code == 400
    assert "자료" in resp.json()["detail"]


def test_no_revision_needed_skips_reviser(client):
    app.dependency_overrides[get_reviewer_llm_call] = lambda: _make_fake_reviewer(needs_revision=False)
    ctx = _create_approved_book(client)

    resp = client.post(f"/api/outlines/{ctx['outline_id']}/units/{ctx['unit_id']}/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["revised"] is False
    assert body["unit"]["status"] == "generated"
    assert "ALD 공정은 온도와 압력에 민감하다" in body["unit"]["body_md"]
    assert body["unit"]["body_version"] == 1
    assert "reviser" not in CALL_LOG
    assert CALL_LOG == ["writer", "reviewer"]


def test_revision_needed_calls_reviser_and_saves_revised_body(client):
    app.dependency_overrides[get_reviewer_llm_call] = lambda: _make_fake_reviewer(needs_revision=True)
    ctx = _create_approved_book(client)

    resp = client.post(f"/api/outlines/{ctx['outline_id']}/units/{ctx['unit_id']}/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["revised"] is True
    assert body["unit"]["status"] == "reviewed"
    assert "수정됨" in body["unit"]["body_md"]
    assert len(body["review"]["issues"]) == 1
    assert CALL_LOG == ["writer", "reviewer", "reviser"]


def test_body_version_increments_on_regenerate(client):
    app.dependency_overrides[get_reviewer_llm_call] = lambda: _make_fake_reviewer(needs_revision=False)
    ctx = _create_approved_book(client)

    first = client.post(
        f"/api/outlines/{ctx['outline_id']}/units/{ctx['unit_id']}/generate"
    ).json()
    assert first["unit"]["body_version"] == 1

    second = client.post(
        f"/api/outlines/{ctx['outline_id']}/units/{ctx['unit_id']}/generate"
    ).json()
    assert second["unit"]["body_version"] == 2
