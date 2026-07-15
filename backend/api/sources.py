import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.skills.research import analyze_source
from backend.services.extractors import SUPPORTED_FILE_TYPES, extract_text, extract_url
from backend.services.llm_client import call_ollama, get_llm_call
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


# ---------------------------------------------------------------------------
# 등록
# ---------------------------------------------------------------------------
def _register_source_content(
    session: Session, book: BookProject, book_id: str, filename: str, content: bytes
) -> SourceDocument:
    """파일 바이트를 실제로 저장하고 SourceDocument를 만드는 단일 소유자.

    upload_source(HTTP 멀티파트로 바이트를 받음)와 register_local_source(서버
    로컬 경로에서 바이트를 읽음)가 이 함수 하나를 공유한다.
    """
    source_type = _infer_source_type(filename)
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
    dest_path = UPLOAD_DIR / f"src-{source_id_placeholder}-{filename}"
    dest_path.write_bytes(content)

    source = SourceDocument(
        workspace_id=book.workspace_id,
        book_id=book_id,
        source_type=source_type,
        title=filename,
        file_path=str(dest_path),
        content_hash=content_hash,
        status="uploaded",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.post("/api/books/{book_id}/sources/upload", response_model=SourceDocument)
async def upload_source(book_id: str, file: UploadFile, session: Session = Depends(get_session)):
    book = _get_book_or_404(session, book_id)
    content = await file.read()
    return _register_source_content(session, book, book_id, file.filename, content)


class RegisterLocalFileRequest(BaseModel):
    file_path: str


@router.post("/api/books/{book_id}/sources/register-local", response_model=SourceDocument)
def register_local_source(
    book_id: str, payload: RegisterLocalFileRequest, session: Session = Depends(get_session)
):
    """이미 서버 디스크에 있는 파일을 브라우저 업로드 없이 바로 등록한다."""
    book = _get_book_or_404(session, book_id)
    src_path = Path(payload.file_path)
    if not src_path.is_file():
        raise HTTPException(400, f"파일을 찾을 수 없습니다: {payload.file_path}")

    content = src_path.read_bytes()
    return _register_source_content(session, book, book_id, src_path.name, content)


class RegisterLocalDirRequest(BaseModel):
    dir_path: str
    recursive: bool = False


@router.post("/api/books/{book_id}/sources/register-local-dir")
def register_local_dir(
    book_id: str,
    payload: RegisterLocalDirRequest,
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    """디렉터리 안의 파일들을 한 번에 자료로 등록하고 곧바로 분석까지 한다.

    지원하지 않는 확장자는 조용히 건너뛰고 skipped에 담는다. 파일 하나가
    실패(등록이든 분석이든)해도 나머지는 계속 진행하고 failed에 담는다.
    이미 분석 완료된 파일은 재분석하지 않는다.
    """
    book = _get_book_or_404(session, book_id)
    dir_path = Path(payload.dir_path)
    if not dir_path.is_dir():
        raise HTTPException(400, f"디렉터리를 찾을 수 없습니다: {payload.dir_path}")

    pattern = "**/*" if payload.recursive else "*"
    registered: list[dict] = []
    skipped: list[str] = []
    failed: list[dict] = []

    for entry in sorted(dir_path.glob(pattern)):
        if not entry.is_file():
            continue

        ext = entry.suffix.lower().lstrip(".")
        if ext not in SUPPORTED_FILE_TYPES:
            skipped.append(entry.name)
            continue

        source = None
        try:
            content = entry.read_bytes()
            source = _register_source_content(session, book, book_id, entry.name, content)
            if source.status != "analyzed":
                _analyze_source(session, source, None, llm_call)
                session.refresh(source)
            registered.append(source.model_dump())
        except Exception as exc:  # noqa: BLE001
            if source is not None:
                source.status = "failed"
                session.add(source)
                session.commit()
            failed.append({"filename": entry.name, "error": str(exc)})

    return {"registered": registered, "skipped": skipped, "failed": failed}


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


# ---------------------------------------------------------------------------
# 분석
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    purpose: Optional[str] = None


def _analyze_source(
    session: Session, source: SourceDocument, purpose: Optional[str], llm_call
) -> SourceProfile:
    """분석 로직의 단일 소유자.

    /api/sources/{id}/analyze 와 register_local_dir 이 이 함수 하나를 공유한다.
    """
    source.status = "analyzing"
    session.add(source)
    session.commit()

    if source.source_type == "url":
        title, text = extract_url(source.url)
        if not source.raw_text:
            source.title = source.title or title
    else:
        if not source.file_path:
            raise ValueError("file_path가 없는 자료입니다")
        text = extract_text(source.file_path, source.source_type)

    source.raw_text = text
    session.add(source)
    session.commit()

    profile_data = analyze_source(text, purpose=purpose, llm_call=llm_call)

    profile = session.exec(
        select(SourceProfile).where(SourceProfile.source_id == source.source_id)
    ).first()
    if profile is None:
        profile = SourceProfile(source_id=source.source_id)

    for field, value in profile_data.items():
        setattr(profile, field, value)

    source.status = "analyzed"
    session.add(source)
    session.add(profile)
    session.commit()
    session.refresh(source)
    session.refresh(profile)
    return profile


@router.post("/api/sources/{source_id}/analyze", response_model=SourceProfile)
def analyze(
    source_id: str,
    payload: AnalyzeRequest = AnalyzeRequest(),
    session: Session = Depends(get_session),
    llm_call=Depends(get_llm_call),
):
    source = _get_source_or_404(session, source_id)
    try:
        return _analyze_source(session, source, payload.purpose, llm_call)
    except Exception as exc:  # noqa: BLE001
        source.status = "failed"
        session.add(source)
        session.commit()
        raise HTTPException(502, f"자료 분석에 실패했습니다: {exc}") from exc


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
    """자료를 삭제한다."""
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
