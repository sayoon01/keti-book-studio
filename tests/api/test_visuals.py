"""Phase 6 완료 조건 테스트.

1. Visual Planner가 존재하지 않는 source_id를 참조하면 걸러짐(환각 방지)
2. Planner가 준 source_id가 실제 프롬프트에 전달되는지 (컬럼 힌트 제공 확인)
3. table 시각자료 생성 시 실제 csv 내용이 그대로 나오는지 (LLM 개입 없음)
4. bar_chart 생성 시 pandas groupby 계산 결과가 수동 계산과 일치하는지
5. diagram은 LLM(mermaid 텍스트)으로, illustration/cover는 501로 라우팅되는지
6. 자료 없는 data 시각자료는 생성 불가
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

from backend.main import app  # noqa: E402
from backend.services.llm_client import get_llm_call, get_writer_llm_call  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


def _fake_planner_llm_with_hallucinated_source(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "visuals": [
                {
                    "visual_type": "bar_chart",
                    "purpose": "파라미터별 중요도 비교",
                    "source_id": "source-존재하지않음",
                    "category_column": "parameter",
                    "value_column": "importance",
                    "caption": "파라미터 중요도",
                    "required": True,
                },
                {
                    "visual_type": "diagram",
                    "purpose": "ALD 사이클 개념도",
                    "source_id": None,
                    "category_column": None,
                    "value_column": None,
                    "caption": "ALD 반응 사이클",
                    "required": False,
                },
            ]
        },
        ensure_ascii=False,
    )


def _make_planner_llm_with_real_source(source_id: str):
    def _llm(system_prompt: str, user_prompt: str) -> str:
        assert source_id in user_prompt
        return json.dumps(
            {
                "visuals": [
                    {
                        "visual_type": "bar_chart",
                        "purpose": "파라미터별 중요도 비교",
                        "source_id": source_id,
                        "category_column": "parameter",
                        "value_column": "importance",
                        "caption": "파라미터 중요도",
                        "required": True,
                    }
                ]
            },
            ensure_ascii=False,
        )

    return _llm


def _fake_diagram_llm(system_prompt: str, user_prompt: str) -> str:
    return "graph TD\nA[전구체 공급] --> B[표면 반응]\nB --> C[퍼지]\nC --> D[반응가스 공급]"


def _fake_research_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "summary": "파라미터 중요도 데이터",
            "main_topics": ["parameter", "importance"],
            "key_findings": ["온도가 가장 중요도가 높음"],
            "tables": [{"description": "파라미터별 중요도", "usable_for_chart": True}],
            "limitations": [],
            "recommended_uses": ["기술서"],
        },
        ensure_ascii=False,
    )


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    app.dependency_overrides[get_writer_llm_call] = lambda: _fake_diagram_llm
    app.dependency_overrides[get_llm_call] = lambda: _fake_research_llm
    yield
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_unit_with_csv_source(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 기술서"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    unit = client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장. 파라미터 비교", "target_characters": 3000},
    ).json()

    csv_content = b"parameter,importance\ntemperature,9\npressure,7\npurge_time,4\n"
    source = client.post(
        f"/api/books/{book['book_id']}/sources/upload",
        files={"file": ("params.csv", csv_content, "text/csv")},
    ).json()
    client.post(f"/api/sources/{source['source_id']}/analyze", json={})

    return {"book": book, "unit": unit, "source": source}


def test_planner_filters_out_hallucinated_source_id(client):
    app.dependency_overrides[get_llm_call] = lambda: _fake_planner_llm_with_hallucinated_source
    ctx = _create_unit_with_csv_source(client)

    resp = client.post(f"/api/units/{ctx['unit']['unit_id']}/visuals/plan")
    assert resp.status_code == 200, resp.text
    visuals = resp.json()

    types = [v["visual_type"] for v in visuals]
    assert "bar_chart" not in types
    assert "diagram" in types


def test_planner_creates_visual_with_real_source(client):
    ctx = _create_unit_with_csv_source(client)
    app.dependency_overrides[get_llm_call] = lambda: _make_planner_llm_with_real_source(
        ctx["source"]["source_id"]
    )

    resp = client.post(f"/api/units/{ctx['unit']['unit_id']}/visuals/plan")
    assert resp.status_code == 200, resp.text
    visuals = resp.json()
    assert len(visuals) == 1
    assert visuals[0]["visual_type"] == "bar_chart"
    assert visuals[0]["source_ids"] == [ctx["source"]["source_id"]]
    assert visuals[0]["status"] == "planned"


def test_generate_table_reads_actual_csv_no_llm_involved(client):
    ctx = _create_unit_with_csv_source(client)

    visual = client.post(
        f"/api/units/{ctx['unit']['unit_id']}/visuals",
        json={"visual_type": "table", "source_ids": [ctx["source"]["source_id"]]},
    ).json()

    resp = client.post(f"/api/visuals/{visual['visual_id']}/generate")
    assert resp.status_code == 200, resp.text
    data = resp.json()["artifact"]["data"]

    assert data["columns"] == ["parameter", "importance"]
    assert data["rows"] == [["temperature", 9], ["pressure", 7], ["purge_time", 4]]
    assert data["total_rows"] == 3


def test_generate_bar_chart_matches_manual_pandas_calc(client):
    ctx = _create_unit_with_csv_source(client)
    app.dependency_overrides[get_llm_call] = lambda: _make_planner_llm_with_real_source(
        ctx["source"]["source_id"]
    )
    visuals = client.post(f"/api/units/{ctx['unit']['unit_id']}/visuals/plan").json()
    visual_id = visuals[0]["visual_id"]

    resp = client.post(f"/api/visuals/{visual_id}/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["artifact"]["type"] == "chart"
    data = body["artifact"]["data"]
    assert data["category_column"] == "parameter"
    assert data["value_column"] == "importance"
    label_to_value = dict(zip(data["labels"], data["values"]))
    assert label_to_value == {"temperature": 9.0, "pressure": 7.0, "purge_time": 4.0}

    assert body["visual"]["status"] == "generated"
    assert body["visual"]["artifact_id"] == body["artifact"]["artifact_id"]


def test_generate_diagram_uses_llm_mermaid_text(client):
    ctx = _create_unit_with_csv_source(client)

    visual = client.post(
        f"/api/units/{ctx['unit']['unit_id']}/visuals",
        json={"visual_type": "diagram", "purpose": "ALD 사이클 개념도"},
    ).json()

    resp = client.post(f"/api/visuals/{visual['visual_id']}/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["artifact"]["type"] == "diagram"
    assert "graph TD" in body["artifact"]["data"]["mermaid"]
    assert body["artifact"]["created_by"] == "visual_agent"


def test_illustration_not_yet_implemented(client):
    ctx = _create_unit_with_csv_source(client)

    visual = client.post(
        f"/api/units/{ctx['unit']['unit_id']}/visuals",
        json={"visual_type": "illustration", "purpose": "표지 삽화"},
    ).json()

    resp = client.post(f"/api/visuals/{visual['visual_id']}/generate")
    assert resp.status_code == 501


def test_data_visual_without_source_fails(client):
    ctx = _create_unit_with_csv_source(client)

    visual = client.post(
        f"/api/units/{ctx['unit']['unit_id']}/visuals",
        json={"visual_type": "bar_chart"},
    ).json()

    resp = client.post(f"/api/visuals/{visual['visual_id']}/generate")
    assert resp.status_code == 400
