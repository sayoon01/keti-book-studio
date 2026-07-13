"""Phase 3 완료 조건 테스트."""

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


def _fake_config_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "document_type": "technical_guide",
            "target_reader": "반도체 공정 엔지니어",
            "purpose": "ALD 파라미터 이해",
            "tone": "전문적이고 근거 중심",
            "expertise_level": "expert",
            "suggested_chapter_count": 8,
            "default_chars_per_chapter": 6000,
            "citation_policy": "source_required",
            "visual_density": "high",
            "recommended_persona_name": "기술 전문가",
            "recommendation_reason": "공정 파라미터 분석 자료이며 전문 용어가 많음",
            "alternative_persona_names": ["데이터 분석가"],
        },
        ensure_ascii=False,
    )


def _dispatching_llm_call(system_prompt: str, user_prompt: str) -> str:
    if "책/문서 기획 전문가" in system_prompt:
        return _fake_config_llm(system_prompt, user_prompt)
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


def test_system_personas_seeded(client):
    personas = client.get("/api/personas").json()
    system_personas = [p for p in personas if p["scope"] == "system"]
    assert len(system_personas) == 3
    names = {p["name"] for p in system_personas}
    assert "기술 전문가" in names


def test_cannot_edit_system_persona_directly(client):
    personas = client.get("/api/personas").json()
    tech_expert = next(p for p in personas if p["name"] == "기술 전문가")

    resp = client.patch(
        f"/api/personas/{tech_expert['persona_id']}/files/PERSONA.md",
        json={"content": "해킹 시도"},
    )
    assert resp.status_code == 400


def test_clone_persona_and_edit(client):
    personas = client.get("/api/personas").json()
    tech_expert = next(p for p in personas if p["name"] == "기술 전문가")

    cloned = client.post(
        "/api/personas",
        json={
            "name": "반도체 전문가 (커스텀)",
            "base_persona_id": tech_expert["persona_id"],
        },
    ).json()

    assert cloned["scope"] == "custom"
    assert cloned["base_persona_id"] == tech_expert["persona_id"]
    assert "기술 문서 전문가" in cloned["file_contents"]["PERSONA.md"]

    edit_resp = client.patch(
        f"/api/personas/{cloned['persona_id']}/files/PERSONA.md",
        json={"content": "# 커스텀 정체성\n\n반도체 8대 공정 전문\n"},
    )
    assert edit_resp.status_code == 200
    assert "반도체 8대 공정 전문" in edit_resp.json()["file_contents"]["PERSONA.md"]


def test_config_suggest_fills_config_and_sets_persona(client):
    book = _create_book_with_analyzed_source(client)

    resp = client.post(f"/api/books/{book['book_id']}/config/suggest", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["config"]["document_type"] == "technical_guide"
    assert body["config"]["target_reader"] == "반도체 공정 엔지니어"
    assert body["config"]["default_chars_per_chapter"] == 6000
    assert body["suggested_chapter_count"] == 8
    assert body["recommendation_reason"]

    assert body["config"]["chapter_count"] == 0
    assert body["config"]["total_target_characters"] == 0

    personas = client.get("/api/personas").json()
    tech_expert_id = next(p for p in personas if p["name"] == "기술 전문가")["persona_id"]
    assert body["book_persona_id"] == tech_expert_id


def test_config_suggest_does_not_override_user_chosen_persona(client):
    book = _create_book_with_analyzed_source(client)

    personas = client.get("/api/personas").json()
    data_analyst_id = next(p for p in personas if p["name"] == "데이터 분석가")["persona_id"]

    client.patch(f"/api/books/{book['book_id']}", json={"persona_id": data_analyst_id})

    resp = client.post(f"/api/books/{book['book_id']}/config/suggest", json={})
    assert resp.json()["book_persona_id"] == data_analyst_id


def test_suggest_without_analyzed_sources_fails(client):
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "빈 책"}).json()
    resp = client.post(f"/api/books/{book['book_id']}/config/suggest", json={})
    assert resp.status_code == 400
