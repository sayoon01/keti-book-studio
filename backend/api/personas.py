from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.services.persona_store import STANDARD_FILES, clone_persona_files, read_persona_files, write_persona_files
from backend.storage.database import get_session
from backend.storage.models import Persona

router = APIRouter(prefix="/api/personas", tags=["personas"])


def _get_persona_or_404(session: Session, persona_id: str) -> Persona:
    persona = session.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "persona not found")
    return persona


def _with_contents(persona: Persona) -> dict:
    return {**persona.model_dump(), "file_contents": read_persona_files(persona.files)}


@router.get("")
def list_personas(session: Session = Depends(get_session)):
    personas = session.exec(select(Persona)).all()
    return [p.model_dump() for p in personas]


@router.get("/{persona_id}")
def get_persona(persona_id: str, session: Session = Depends(get_session)):
    persona = _get_persona_or_404(session, persona_id)
    return _with_contents(persona)


class PersonaCreateRequest(BaseModel):
    name: str
    base_persona_id: Optional[str] = None
    description: Optional[str] = None


@router.post("")
def create_persona(payload: PersonaCreateRequest, session: Session = Depends(get_session)):
    persona = Persona(
        scope="custom",
        name=payload.name,
        base_persona_id=payload.base_persona_id,
        created_by="user",
    )
    session.add(persona)
    session.commit()
    session.refresh(persona)

    if payload.base_persona_id:
        base = _get_persona_or_404(session, payload.base_persona_id)
        file_paths = clone_persona_files(base.persona_id, persona.persona_id)
    else:
        blank = {f: f"# {payload.name}\n\n(내용을 작성해주세요)\n" for f in STANDARD_FILES}
        file_paths = write_persona_files(persona.persona_id, blank)

    persona.files = file_paths
    if payload.description:
        persona.defaults = {**(persona.defaults or {}), "description": payload.description}

    session.add(persona)
    session.commit()
    session.refresh(persona)
    return _with_contents(persona)


class PersonaFileUpdateRequest(BaseModel):
    content: str


@router.patch("/{persona_id}/files/{filename}")
def update_persona_file(
    persona_id: str,
    filename: str,
    payload: PersonaFileUpdateRequest,
    session: Session = Depends(get_session),
):
    persona = _get_persona_or_404(session, persona_id)
    if persona.scope == "system":
        raise HTTPException(400, "기본 제공 Persona는 직접 수정할 수 없습니다. 복제해서 수정해주세요.")

    file_paths = dict(persona.files)
    file_paths.update(write_persona_files(persona.persona_id, {filename: payload.content}))
    persona.files = file_paths

    session.add(persona)
    session.commit()
    session.refresh(persona)
    return _with_contents(persona)
