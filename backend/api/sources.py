import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.skills.research import analyze_source
from backend.services.extractors import SUPPORTED_FILE_TYPES, extract_text, extract_url
from backend.services.llm_client import get_llm_call
from backend.storage.database import get_session
from backend.storage.models import BookProject, SourceDocument, SourceProfile

router = APIRouter(tags=["sources"])

UPLOAD_DIR = Path(os.environ.get("KETI_UPLOAD_DIR", "data/uploads"))


def _get_book_or_404(session: Session, book_id: str) -> BookProject:
    book = session.get(BookProject, book_id)
    if not book:
        raise HTTPException(404, "book not found")
    return book


def _get_source_or_404(session: Session, source_id: str) -> SourceDocument:
    source = session.get(SourceDocument, source_id)
    if not source:
        raise HTTPException(404, "source not found")
    return source


def _infer_source_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            400,
            f"지원하지 않는 파일 형식입니다: .{ext} "
            f"(현재 지원: {', '.join(sorted(SUPPORTED_FILE_TYPES))})",
        )
    return ext


@router.post("/api/books/{book_id}/sources/upload", response_model=SourceDocument)
async def upload_source(book_id: str, file: UploadFile, session: Session = Depends(get_session)):
    book = _get_book_or_404(session, book_id)
    source_type = _infer_source_type(file.filename)

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    existing = session.exec(
        select(SourceDocument).where(
            SourceDocument.workspace_id == book.workspace_id,
            SourceDocument.content_hash == content_hash,
        )
    ).first()
    if existing:
        return existing

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    source_id_placeholder = hashlib.sha256(content_hash.encode()).hexdigest()[:12]
    dest_path = UPLOAD_DIR / f"src-{source_id_placeholder}-{file.filename}"
    dest_path.write_bytes(content)

    source = SourceDocument(
        workspace_id=book.workspace_id,
        book_id=book_id,
        source_type=source_type,
        title=file.filename,
        file_path=str(dest_path),
        content_hash=content_hash,
        status="uploaded",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


class RegisterUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None


@router.post("/api/books/{book_id}/sources/url", response_model=SourceDocument)
def register_url_source(
    book_id: str, payload: RegisterUrlRequest, session: Session = Depends(get_session)
):
    book = _get_book_or_404(session, book_id)

    content_hash = hashlib.sha256(payload.url.encode()).hexdigest()
    existing = session.exec(
        select(SourceDocument).where(
            SourceDocument.workspace_id == book.workspace_id,
            SourceDocument.content_hash == content_hash,
        )
    ).first()
    if existing:
        return existing

    source = SourceDocument(
        workspace_id=book.workspace_id,
        book_id=book_id,
        source_type="url",
        title=payload.title or payload.url,
        url=payload.url,
        content_hash=content_hash,
        status="uploaded",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.get("/api/books/{book_id}/sources", response_model=list[SourceDocument])
def list_sources(book_id: str, session: Session = Depends(get_session)):
    return session.exec(select(SourceDocument).where(SourceDocument.book_id == book_id)).all()


class AnalyzeRequest(BaseModel):
    purpose: Optional[str] = None


@router.post("/api/sources/{source_id}/analyze", response_model=SourceProfile)
def analyze(
    source_id: str,
    payload: AnalyzeRequest = AnalyzeRequest(),
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    source = _get_source_or_404(session, source_id)

    source.status = "analyzing"
    session.add(source)
    session.commit()

    try:
        if source.source_type == "url":
            title, text = extract_url(source.url)
            if not source.raw_text:
                source.title = source.title or title
        else:
            if not source.file_path:
                raise HTTPException(400, "file_path가 없는 자료입니다")
            text = extract_text(source.file_path, source.source_type)

        source.raw_text = text
        session.add(source)
        session.commit()

        profile_data = analyze_source(text, purpose=payload.purpose, llm_call=llm_call)

    except HTTPException:
        raise
    except Exception as exc:
        source.status = "failed"
        session.add(source)
        session.commit()
        raise HTTPException(502, f"자료 분석에 실패했습니다: {exc}") from exc

    profile = session.exec(
        select(SourceProfile).where(SourceProfile.source_id == source_id)
    ).first()
    if profile is None:
        profile = SourceProfile(source_id=source_id)

    for field, value in profile_data.items():
        setattr(profile, field, value)

    source.status = "analyzed"
    session.add(source)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/api/sources/{source_id}/profile", response_model=SourceProfile)
def get_profile(source_id: str, session: Session = Depends(get_session)):
    profile = session.exec(
        select(SourceProfile).where(SourceProfile.source_id == source_id)
    ).first()
    if not profile:
        raise HTTPException(404, "이 자료는 아직 분석되지 않았습니다")
    return profile


@router.delete("/api/sources/{source_id}", status_code=204)
def delete_source(source_id: str, session: Session = Depends(get_session)):
    """자료를 삭제한다.

    SourceProfile(분석 결과)이 SQLModel Relationship cascade로 묶여있지 않아서
    (source_documents <- source_profiles 는 FK만 있고 ORM cascade 없음),
    여기서 직접 같이 지운다 - 안 그러면 고아 SourceProfile 행이 남는다.
    업로드된 실제 파일도 같이 지운다 (URL 소스는 file_path가 없어서 건너뜀).
    """
    source = _get_source_or_404(session, source_id)

    profile = session.exec(
        select(SourceProfile).where(SourceProfile.source_id == source_id)
    ).first()
    if profile:
        session.delete(profile)

    if source.file_path:
        Path(source.file_path).unlink(missing_ok=True)

    session.delete(source)
    session.commit()
