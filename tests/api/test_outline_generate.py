"""Phase 4 완료 조건 테스트."""

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
from backend.services.llm_client import get_llm_call  # noqa: E402
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
                    "target_characters": 5000,
                    "must_cover": ["정의", "반응 사이클"],
                },
                {
                    "title": "2장. 주요 파라미터",
                    "description": "온도와 압력의 영향",
                    "target_characters": 6000,
                    "must_cover": ["온도", "압력"],
                },
                {
                    "title": "3장. 공정 최적화",
                    "description": "파라미터 제어 전략",
                    "target_characters": 5500,
                    "must_cover": ["제어 전략"],
                },
            ]
        },
        ensure_ascii=False,
    )


def _dispatching_llm_call(system_prompt: str, user_prompt: str) -> str:
    if "목차를 설계하는 전문 편집자" in system_prompt:
        return _fake_outline_llm(system_prompt, user_prompt)
    return _fake_research_llm(system_prompt, user_prompt)


@pytest.fixture(autouse=True)
def _reset_db():
    from backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    app.dependency_overrides[get_llm_call] = lambda: _dispatching_llm_call
    yield
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book_with_analyzed_source(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 기술서"}).json()
    source = client.post(
        f"/api/books/{book['book_id']}/sources/upload",
        files={"file": ("note.txt", b"ALD process notes", "text/plain")},
    ).json()
    client.post(f"/api/sources/{source['source_id']}/analyze", json={})
    return book


def _set_persona(client, book_id: str) -> None:
    personas = client.get("/api/personas").json()
    tech_expert_id = next(p for p in personas if p["name"] == "기술 전문가")["persona_id"]
    client.patch(f"/api/books/{book_id}", json={"persona_id": tech_expert_id})


def test_generate_outline_requires_persona(client):
    book = _create_book_with_analyzed_source(client)
    resp = client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    assert resp.status_code == 400
    assert "Persona" in resp.json()["detail"]


def test_generate_outline_requires_analyzed_sources(client):
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "빈 책"}).json()
    _set_persona(client, book["book_id"])
    resp = client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    assert resp.status_code == 400
    assert "자료" in resp.json()["detail"]


def test_generate_outline_creates_units_and_recalculates_config(client):
    book = _create_book_with_analyzed_source(client)
    _set_persona(client, book["book_id"])

    resp = client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["units"]) == 3
    assert body["units"][0]["title"] == "1장. ALD 공정 개요"
    assert body["outline"]["status"] == "draft"

    config = client.get(f"/api/books/{book['book_id']}/config").json()
    assert config["total_target_characters"] == 5000 + 6000 + 5500
    assert config["chapter_count"] == 3


def test_regenerating_approved_outline_reverts_to_draft(client):
    book = _create_book_with_analyzed_source(client)
    _set_persona(client, book["book_id"])
    client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    client.post(f"/api/books/{book['book_id']}/outline/approve")

    resp = client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    assert resp.json()["outline"]["status"] == "draft"


def test_unit_generate_blocked_before_approval(client):
    book = _create_book_with_analyzed_source(client)
    _set_persona(client, book["book_id"])
    outline_data = client.post(f"/api/books/{book['book_id']}/outline/generate", json={}).json()
    outline_id = outline_data["outline"]["outline_id"]
    unit_id = outline_data["units"][0]["unit_id"]

    resp = client.post(f"/api/outlines/{outline_id}/units/{unit_id}/generate")
    assert resp.status_code == 403


def test_unit_generate_gate_passes_after_approval(client):
    """승인 가드만 확인 — 실제 Writer/Reviewer/Reviser 파이프라인 상세 검증은
    tests/api/test_writer_pipeline.py 에서 별도로 다룬다."""
    from backend.services.llm_client import get_reviewer_llm_call, get_reviser_llm_call, get_writer_llm_call

    app.dependency_overrides[get_writer_llm_call] = lambda: (lambda s, u: "## 본문\n\n임시 본문입니다.")
    app.dependency_overrides[get_reviewer_llm_call] = lambda: (
        lambda s, u: json.dumps({"issues": [], "needs_revision": False, "overall_comment": "ok"})
    )
    app.dependency_overrides[get_reviser_llm_call] = lambda: (lambda s, u: "수정본")

    book = _create_book_with_analyzed_source(client)
    _set_persona(client, book["book_id"])
    outline_data = client.post(f"/api/books/{book['book_id']}/outline/generate", json={}).json()
    outline_id = outline_data["outline"]["outline_id"]
    unit_id = outline_data["units"][0]["unit_id"]

    client.post(f"/api/books/{book['book_id']}/outline/approve")

    resp = client.post(f"/api/outlines/{outline_id}/units/{unit_id}/generate")
    assert resp.status_code == 200, resp.text


def test_dry_run_returns_chapters_without_touching_db(client):
    """dry_run=True 는 LLM 제안만 반환하고 DB는 전혀 안 바뀌어야 한다."""
    book = _create_book_with_analyzed_source(client)
    _set_persona(client, book["book_id"])

    client.post(f"/api/books/{book['book_id']}/outline/generate", json={})
    before = client.get(f"/api/books/{book['book_id']}/outline").json()
    before_unit_ids = {u["unit_id"] for u in before["units"]}
    assert len(before_unit_ids) == 3

    resp = client.post(
        f"/api/books/{book['book_id']}/outline/generate", json={"dry_run": True}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "outline" not in body
    assert len(body["chapters"]) == 3
    assert all("unit_id" not in ch for ch in body["chapters"])
    assert all(k in body["chapters"][0] for k in ["title", "description", "target_characters"])

    after = client.get(f"/api/books/{book['book_id']}/outline").json()
    after_unit_ids = {u["unit_id"] for u in after["units"]}
    assert after_unit_ids == before_unit_ids
    assert after["outline"]["status"] == before["outline"]["status"]


def test_dry_run_still_validates_persona_and_sources(client):
    """미리보기여도 검증(페르소나/분석자료)은 그대로 걸려야 한다."""
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "빈 책"}).json()

    resp = client.post(
        f"/api/books/{book['book_id']}/outline/generate", json={"dry_run": True}
    )
    assert resp.status_code == 400
