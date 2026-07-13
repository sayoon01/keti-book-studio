import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.services.exporters import render_docx, render_markdown, render_pdf
from backend.services.github_client import create_repo, get_github_token, upload_file
from backend.storage.database import get_session
from backend.storage.models import BookOutline, BookProject, BookUnit, ExportJob

router = APIRouter(tags=["exports"])

EXPORT_DIR = Path(os.environ.get("KETI_EXPORT_DIR", "data/exports"))

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "markdown": "text/markdown",
}
EXTENSIONS = {"pdf": "pdf", "docx": "docx", "markdown": "md"}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug or "book"


def _build_export_file(
    book_id: str, format: str, options: dict, session: Session
) -> tuple[ExportJob, BookProject, Path]:
    """ExportJob 레코드를 만들고 실제 파일을 디스크에 생성한다.

    로컬 다운로드(export_book)와 GitHub 업로드(export_to_github)가
    이 함수 하나를 공유한다.
    """
    if format not in EXTENSIONS:
        raise HTTPException(400, f"지원하지 않는 형식입니다: {format}")

    book = session.get(BookProject, book_id)
    if not book:
        raise HTTPException(404, "book not found")

    outline = session.exec(select(BookOutline).where(BookOutline.book_id == book_id)).first()
    units = (
        session.exec(
            select(BookUnit).where(BookUnit.outline_id == outline.outline_id).order_by(BookUnit.order)
        ).all()
        if outline
        else []
    )
    if not units:
        raise HTTPException(400, "목차가 비어 있습니다. 먼저 챕터를 만들어주세요.")

    units_data = [u.model_dump() for u in units]

    export = ExportJob(book_id=book_id, format=format, options=options, status="running")
    session.add(export)
    session.commit()
    session.refresh(export)

    markdown_text = render_markdown(
        book.title, units_data, include_toc=options.get("include_toc", True)
    )

    book_dir = EXPORT_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    dest_path = book_dir / f"{export.export_id}.{EXTENSIONS[format]}"

    try:
        if format == "markdown":
            dest_path.write_text(markdown_text, encoding="utf-8")
        elif format == "docx":
            render_docx(markdown_text, str(dest_path), book.title)
        elif format == "pdf":
            render_pdf(markdown_text, str(dest_path), book.title)
    except Exception as exc:
        export.status = "failed"
        session.add(export)
        session.commit()
        raise HTTPException(500, f"보내기에 실패했습니다: {exc}") from exc

    export.status = "done"
    export.result_path = str(dest_path)
    session.add(export)
    session.commit()
    session.refresh(export)

    return export, book, dest_path


class ExportRequest(BaseModel):
    format: str
    include_toc: bool = True


@router.post("/api/books/{book_id}/export", response_model=ExportJob)
def export_book(book_id: str, payload: ExportRequest, session: Session = Depends(get_session)):
    export, _book, _path = _build_export_file(book_id, payload.format, payload.model_dump(), session)
    return export


@router.get("/api/books/{book_id}/exports", response_model=list[ExportJob])
def list_exports(book_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(ExportJob).where(ExportJob.book_id == book_id).order_by(ExportJob.created_at.desc())
    ).all()


@router.get("/api/exports/{export_id}/download")
def download_export(export_id: str, session: Session = Depends(get_session)):
    export = session.get(ExportJob, export_id)
    if not export or export.status != "done" or not export.result_path:
        raise HTTPException(404, "다운로드할 파일이 없습니다.")
    if not Path(export.result_path).exists():
        raise HTTPException(404, "파일이 디스크에서 사라졌습니다.")

    filename = f"book.{EXTENSIONS[export.format]}"
    return FileResponse(
        export.result_path, media_type=MEDIA_TYPES[export.format], filename=filename
    )


class GithubExportRequest(BaseModel):
    format: str
    repo_owner: str
    repo_name: str
    path: Optional[str] = None
    branch: str = "main"
    commit_message: Optional[str] = None
    create_repo: bool = False
    private: bool = True


@router.post("/api/books/{book_id}/export/github")
def export_to_github(
    book_id: str, payload: GithubExportRequest, session: Session = Depends(get_session)
):
    """책을보낸 뒤 GitHub 저장소에 그대로 커밋한다.

    같은 경로에 파일이 이미 있으면 새 커밋으로 덮어쓰고, 없으면 새로 만든다.
    """
    try:
        token = get_github_token()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc

    export, book, dest_path = _build_export_file(
        book_id, payload.format, {"include_toc": True}, session
    )

    if payload.create_repo:
        try:
            create_repo(name=payload.repo_name, private=payload.private, token=token)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc

    file_path_in_repo = payload.path or f"{_slugify(book.title)}.{EXTENSIONS[payload.format]}"
    content_bytes = Path(dest_path).read_bytes()
    message = payload.commit_message or f"Add/update {book.title}"

    try:
        result = upload_file(
            owner=payload.repo_owner,
            repo=payload.repo_name,
            path=file_path_in_repo,
            content_bytes=content_bytes,
            message=message,
            branch=payload.branch,
            token=token,
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

    github_url = (
        f"https://github.com/{payload.repo_owner}/{payload.repo_name}"
        f"/blob/{payload.branch}/{file_path_in_repo}"
    )

    return {
        "export": export,
        "github_url": github_url,
        "commit_sha": (result.get("commit") or {}).get("sha"),
    }
