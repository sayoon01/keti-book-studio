from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.skills.diagram import generate_diagram
from backend.skills.visual_planner import plan_visuals
from backend.services.data_tools import compute_chart_data, get_columns, load_table
from backend.services.llm_client import get_llm_call, get_writer_llm_call
from backend.services.persona_store import read_persona_files
from backend.storage.database import get_session
from backend.storage.models import (
    Artifact,
    BookOutline,
    BookProject,
    BookUnit,
    Persona,
    SourceDocument,
    VisualRequest,
)

router = APIRouter(tags=["visuals"])

DATA_VISUAL_TYPES = {"table", "bar_chart", "line_chart", "scatter"}
TABULAR_SOURCE_TYPES = {"csv", "xlsx"}


def _get_unit_or_404(session: Session, unit_id: str) -> BookUnit:
    unit = session.get(BookUnit, unit_id)
    if not unit:
        raise HTTPException(404, "unit not found")
    return unit


def _get_visual_or_404(session: Session, visual_id: str) -> VisualRequest:
    visual = session.get(VisualRequest, visual_id)
    if not visual:
        raise HTTPException(404, "visual not found")
    return visual


@router.post("/api/units/{unit_id}/visuals/plan")
def plan_unit_visuals(
    unit_id: str,
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    unit = _get_unit_or_404(session, unit_id)
    outline = session.get(BookOutline, unit.outline_id)
    book = session.get(BookProject, outline.book_id)

    persona_id = unit.persona_id or book.persona_id
    persona = session.get(Persona, persona_id) if persona_id else None
    visual_policy_md = read_persona_files(persona.files).get("visual_policy.md", "") if persona else ""

    tabular_docs = session.exec(
        select(SourceDocument).where(
            SourceDocument.book_id == outline.book_id,
            SourceDocument.status == "analyzed",
            SourceDocument.source_type.in_(TABULAR_SOURCE_TYPES),
        )
    ).all()

    tabular_sources = []
    for doc in tabular_docs:
        try:
            cols = get_columns(doc.file_path, doc.source_type)
            tabular_sources.append({"source_id": doc.source_id, "columns": cols})
        except Exception:
            continue

    proposals = plan_visuals(
        unit=unit.model_dump(),
        tabular_sources=tabular_sources,
        persona_visual_policy_md=visual_policy_md,
        llm_call=llm_call,
    )

    valid_source_ids = {s["source_id"] for s in tabular_sources}
    created = []
    for p in proposals:
        source_id = p.get("source_id")
        if p["visual_type"] in DATA_VISUAL_TYPES and source_id not in valid_source_ids:
            continue

        data_reference = None
        if p["visual_type"] in DATA_VISUAL_TYPES:
            data_reference = {
                "category_column": p.get("category_column"),
                "value_column": p.get("value_column"),
            }

        vr = VisualRequest(
            unit_id=unit_id,
            visual_type=p["visual_type"],
            purpose=p["purpose"],
            source_ids=[source_id] if source_id else [],
            data_reference=data_reference,
            caption=p["caption"],
            required=p["required"],
            status="planned",
        )
        session.add(vr)
        created.append(vr)

    session.commit()
    for vr in created:
        session.refresh(vr)
    return created


@router.get("/api/units/{unit_id}/visuals")
def list_unit_visuals(unit_id: str, session: Session = Depends(get_session)):
    return session.exec(select(VisualRequest).where(VisualRequest.unit_id == unit_id)).all()


class VisualCreateRequest(BaseModel):
    visual_type: str
    purpose: str = ""
    source_ids: list[str] = []
    data_reference: Optional[dict] = None
    caption: str = ""
    required: bool = False


@router.post("/api/units/{unit_id}/visuals")
def create_visual(
    unit_id: str, payload: VisualCreateRequest, session: Session = Depends(get_session)
):
    _get_unit_or_404(session, unit_id)
    visual = VisualRequest(unit_id=unit_id, status="planned", **payload.model_dump())
    session.add(visual)
    session.commit()
    session.refresh(visual)
    return visual


class VisualUpdateRequest(BaseModel):
    purpose: Optional[str] = None
    caption: Optional[str] = None
    required: Optional[bool] = None
    status: Optional[str] = None
    data_reference: Optional[dict] = None
    source_ids: Optional[list[str]] = None


@router.patch("/api/visuals/{visual_id}")
def update_visual(
    visual_id: str, payload: VisualUpdateRequest, session: Session = Depends(get_session)
):
    visual = _get_visual_or_404(session, visual_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(visual, field, value)
    session.add(visual)
    session.commit()
    session.refresh(visual)
    return visual


@router.post("/api/visuals/{visual_id}/generate")
def generate_visual(
    visual_id: str,
    session: Session = Depends(get_session),
    diagram_llm=Depends(get_writer_llm_call),
):
    visual = _get_visual_or_404(session, visual_id)
    unit = session.get(BookUnit, visual.unit_id)

    if visual.visual_type in DATA_VISUAL_TYPES:
        if not visual.source_ids:
            raise HTTPException(400, "이 시각자료에 연결된 자료가 없습니다.")
        source = session.get(SourceDocument, visual.source_ids[0])
        if not source or source.source_type not in TABULAR_SOURCE_TYPES:
            raise HTTPException(400, "표/차트는 csv 또는 xlsx 자료에서만 생성할 수 있습니다.")

        ref = visual.data_reference or {}
        try:
            if visual.visual_type == "table":
                data = load_table(source.file_path, source.source_type, sheet=ref.get("sheet"))
            else:
                data = compute_chart_data(
                    source.file_path,
                    source.source_type,
                    category_column=ref.get("category_column"),
                    value_column=ref.get("value_column"),
                    sheet=ref.get("sheet"),
                )
        except Exception as exc:
            raise HTTPException(400, f"데이터 처리 실패: {exc}") from exc

        artifact = Artifact(
            type="table" if visual.visual_type == "table" else "chart",
            created_by="data_agent",
            unit_id=visual.unit_id,
            source_ids=visual.source_ids,
            data=data,
        )

    elif visual.visual_type == "diagram":
        mermaid = generate_diagram(purpose=visual.purpose, unit=unit.model_dump(), llm_call=diagram_llm)
        artifact = Artifact(
            type="diagram",
            created_by="visual_agent",
            unit_id=visual.unit_id,
            source_ids=visual.source_ids,
            data={"mermaid": mermaid},
        )

    elif visual.visual_type in {"illustration", "cover"}:
        raise HTTPException(
            501,
            "이미지 생성 파이프라인(표지/삽화)은 아직 연동되지 않았습니다. "
            "로컬 Ollama는 이미지 생성을 지원하지 않아 별도 이미지 모델 연동이 필요합니다.",
        )
    else:
        raise HTTPException(400, f"알 수 없는 visual_type: {visual.visual_type}")

    session.add(artifact)
    session.commit()
    session.refresh(artifact)

    visual.artifact_id = artifact.artifact_id
    visual.status = "generated"
    session.add(visual)
    session.commit()
    session.refresh(visual)
    session.refresh(artifact)  # 위 commit으로 인해 만료된 artifact를 다시 채운다

    return {"visual": visual, "artifact": artifact}
