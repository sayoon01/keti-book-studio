from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import Session

from backend.api.schemas.source_library import (
    AnalyzeCollectionRequest,
    AnalyzeCollectionResponse,
    ApiMessage,
    BookSourceCollectionRead,
    DirectoryUploadResult,
    LinkCollectionToBookRequest,
    SourceCollectionRead,
    SourceCollectionTreeResponse,
    UnitSourceLinkCreate,
    UnitSourceLinkRead,
)
from backend.services.directory_upload_service import (
    DirectoryUploadService,
)
from backend.services.source_library_service import (
    SourceLibraryService,
)
from backend.storage.database import get_session
from backend.storage.repositories.source_repository import (
    SourceLibraryRepository,
)
from backend.storage.models_sources import (
    BookSourceCollection,
    SourceAssignmentType,
    UnitSourceLink,
)


router = APIRouter(
    prefix="/api/source-library",
    tags=["source-library"],
)


def to_collection_read(collection) -> SourceCollectionRead:
    return SourceCollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        collection_type=collection.collection_type,
        status=collection.status,
        root_name=collection.root_name,
        total_files=collection.total_files,
        supported_files=collection.supported_files,
        skipped_files=collection.skipped_files,
        failed_files=collection.failed_files,
        total_size_bytes=collection.total_size_bytes,
        summary=collection.summary,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get(
    "/collections",
    response_model=list[SourceCollectionRead],
)
def list_collections(
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    return [
        to_collection_read(collection)
        for collection in repository.list_collections()
    ]


@router.get(
    "/collections/{collection_id}",
    response_model=SourceCollectionRead,
)
def get_collection(
    collection_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)
    collection = repository.get_collection(collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자료 컬렉션을 찾을 수 없습니다.",
        )

    return to_collection_read(collection)


@router.get(
    "/collections/{collection_id}/tree",
    response_model=SourceCollectionTreeResponse,
)
def get_collection_tree(
    collection_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)
    collection = repository.get_collection(collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자료 컬렉션을 찾을 수 없습니다.",
        )

    service = SourceLibraryService(session)

    return SourceCollectionTreeResponse(
        collection=to_collection_read(collection),
        roots=service.build_collection_tree(collection_id),
    )


@router.post(
    "/collections/{collection_id}/analyze",
    response_model=AnalyzeCollectionResponse,
)
def analyze_collection(
    collection_id: str,
    payload: AnalyzeCollectionRequest,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)
    collection = repository.get_collection(collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자료 컬렉션을 찾을 수 없습니다.",
        )

    try:
        service = SourceLibraryService(session)

        result = service.analyze_collection(
            collection_id=collection_id,
            workspace_id=payload.workspace_id,
            book_id=payload.book_id,
        )

        return AnalyzeCollectionResponse(
            collection_id=result.collection_id,
            total_files=result.total_files,
            completed_files=result.completed_files,
            skipped_files=result.skipped_files,
            failed_files=result.failed_files,
            document_ids=result.document_ids,
            warnings=result.warnings,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/collections/directory",
    response_model=DirectoryUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_directory(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    collection_name: str = Form(...),
    root_name: str = Form(...),
    description: str | None = Form(default=None),
    book_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    try:
        service = DirectoryUploadService(session)

        result = await service.upload_directory(
            files=files,
            relative_paths=relative_paths,
            collection_name=collection_name,
            root_name=root_name,
            book_id=book_id,
            description=description,
        )

        return DirectoryUploadResult(
            collection=to_collection_read(result.collection),
            uploaded_files=result.uploaded_files,
            skipped_files=result.skipped_files,
            failed_files=result.failed_files,
            warnings=result.warnings,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/books/{book_id}/collections/{collection_id}",
    response_model=BookSourceCollectionRead,
)
def link_collection_to_book(
    book_id: str,
    collection_id: str,
    payload: LinkCollectionToBookRequest,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    collection = repository.get_collection(collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자료 컬렉션을 찾을 수 없습니다.",
        )

    link = repository.link_collection_to_book(
        BookSourceCollection(
            book_id=book_id,
            collection_id=collection_id,
            purpose=payload.purpose,
            priority=payload.priority,
            linked_by="USER",
        )
    )

    return BookSourceCollectionRead.model_validate(link)


@router.get(
    "/books/{book_id}/collections",
    response_model=list[BookSourceCollectionRead],
)
def list_book_collections(
    book_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    links = repository.list_book_collection_links(book_id)
    return [
        BookSourceCollectionRead.model_validate(link)
        for link in links
    ]


@router.delete(
    "/books/{book_id}/collections/{collection_id}",
    response_model=ApiMessage,
)
def unlink_collection_from_book(
    book_id: str,
    collection_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    removed = repository.unlink_collection_from_book(
        book_id,
        collection_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="연결된 자료 컬렉션을 찾을 수 없습니다.",
        )

    return ApiMessage(
        message="현재 책에서 자료 컬렉션 연결을 해제했습니다.",
        details={
            "book_id": book_id,
            "collection_id": collection_id,
        },
    )


@router.post(
    "/units/{unit_id}/sources",
    response_model=UnitSourceLinkRead,
)
def link_source_to_unit(
    unit_id: str,
    payload: UnitSourceLinkCreate,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    link = repository.add_unit_source_link(
        UnitSourceLink(
            unit_id=unit_id,
            source_document_id=payload.source_document_id,
            usage_type=payload.usage_type,
            priority=payload.priority,
            required=payload.required,
            assigned_by=SourceAssignmentType.USER.value,
            assignment_reason=payload.assignment_reason,
        )
    )

    return UnitSourceLinkRead.model_validate(link)


@router.get(
    "/units/{unit_id}/sources",
    response_model=list[UnitSourceLinkRead],
)
def list_unit_sources(
    unit_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    links = repository.list_unit_source_links(unit_id)

    return [
        UnitSourceLinkRead.model_validate(link)
        for link in links
    ]


@router.delete(
    "/units/{unit_id}/sources/{source_document_id}",
    response_model=ApiMessage,
)
def unlink_source_from_unit(
    unit_id: str,
    source_document_id: str,
    session: Session = Depends(get_session),
):
    repository = SourceLibraryRepository(session)

    removed = repository.remove_unit_source_link(
        unit_id,
        source_document_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터에 연결된 자료를 찾을 수 없습니다.",
        )

    return ApiMessage(
        message="챕터에서 자료 연결을 해제했습니다.",
        details={
            "unit_id": unit_id,
            "source_document_id": source_document_id,
        },
    )
