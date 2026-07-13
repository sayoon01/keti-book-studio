from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.storage.database import get_session
from backend.storage.models import (
    BookConfig,
    BookOutline,
    BookProject,
    BookProjectCreate,
    BookProjectRead,
    BookProjectUpdate,
)

router = APIRouter(prefix="/api/books", tags=["books"])


@router.post("", response_model=BookProjectRead)
def create_book(payload: BookProjectCreate, session: Session = Depends(get_session)):
    book = BookProject.model_validate(payload)
    session.add(book)
    session.commit()
    session.refresh(book)

    config = BookConfig(book_id=book.book_id)
    outline = BookOutline(book_id=book.book_id)
    session.add(config)
    session.add(outline)
    session.commit()

    return book


@router.get("", response_model=list[BookProjectRead])
def list_books(workspace_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(BookProject).where(BookProject.workspace_id == workspace_id)
    ).all()


@router.get("/{book_id}", response_model=BookProjectRead)
def get_book(book_id: str, session: Session = Depends(get_session)):
    book = session.get(BookProject, book_id)
    if not book:
        raise HTTPException(404, "book not found")
    return book


@router.patch("/{book_id}", response_model=BookProjectRead)
def update_book(book_id: str, payload: BookProjectUpdate, session: Session = Depends(get_session)):
    book = session.get(BookProject, book_id)
    if not book:
        raise HTTPException(404, "book not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)

    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: str, session: Session = Depends(get_session)):
    book = session.get(BookProject, book_id)
    if not book:
        raise HTTPException(404, "book not found")
    session.delete(book)
    session.commit()