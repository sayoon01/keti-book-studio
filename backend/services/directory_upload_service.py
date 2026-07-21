from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile
from sqlmodel import Session

from backend.services.file_storage import save_upload_file
from backend.services.path_safety import (
    normalize_relative_path,
    safe_join,
)
from backend.settings import (
    ALLOWED_SOURCE_EXTENSIONS,
    IGNORED_DIRECTORY_NAMES,
    IGNORED_FILE_NAMES,
    MAX_DIRECTORY_FILES,
    MAX_DIRECTORY_TOTAL_BYTES,
    MAX_SINGLE_FILE_BYTES,
    SOURCE_LIBRARY_DIR,
)
from backend.storage.model_utils import json_dumps
from backend.storage.repositories.source_repository import (
    SourceLibraryRepository,
)
from backend.storage.models_sources import (
    BookSourceCollection,
    SourceCollection,
    SourceCollectionStatus,
    SourceCollectionType,
    SourceNode,
    SourceNodeStatus,
    SourceNodeType,
)


@dataclass
class DirectoryUploadSummary:
    collection: SourceCollection
    uploaded_files: int
    skipped_files: int
    failed_files: int
    warnings: list[str]


class DirectoryUploadService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SourceLibraryRepository(session)

    async def upload_directory(
        self,
        *,
        files: list[UploadFile],
        relative_paths: list[str],
        collection_name: str,
        root_name: str,
        book_id: str | None = None,
        description: str | None = None,
    ) -> DirectoryUploadSummary:
        self._validate_request(files, relative_paths)

        collection = SourceCollection(
            name=collection_name.strip(),
            description=description,
            collection_type=SourceCollectionType.DIRECTORY_UPLOAD.value,
            status=SourceCollectionStatus.UPLOADING.value,
            root_name=root_name.strip(),
        )
        collection = self.repository.add_collection(collection)

        collection_root = (
            SOURCE_LIBRARY_DIR / f"collection-{collection.id}"
        )
        files_root = collection_root / "files"
        manifest_path = collection_root / "manifest.json"

        files_root.mkdir(parents=True, exist_ok=True)

        collection.storage_path = str(collection_root)
        collection.manifest_path = str(manifest_path)
        self.repository.save_collection(collection)

        if book_id:
            self.repository.link_collection_to_book(
                BookSourceCollection(
                    book_id=book_id,
                    collection_id=collection.id,
                    linked_by="USER",
                )
            )

        normalized_items = self._normalize_upload_items(
            files,
            relative_paths,
        )

        directory_nodes = self._build_directory_nodes(
            collection_id=collection.id,
            relative_paths=[
                relative_path
                for _, relative_path in normalized_items
            ],
        )

        if directory_nodes:
            self.repository.add_nodes(directory_nodes)

        node_by_path = {
            node.relative_path: node
            for node in self.repository.list_nodes(collection.id)
        }

        uploaded_count = 0
        skipped_count = 0
        failed_count = 0
        total_size = 0
        warnings: list[str] = []
        manifest_files: list[dict] = []

        for sort_order, (upload, relative_path) in enumerate(
            normalized_items
        ):
            path = PurePosixPath(relative_path)
            parent_path = (
                path.parent.as_posix()
                if path.parent.as_posix() != "."
                else None
            )

            parent_node = (
                node_by_path.get(parent_path)
                if parent_path
                else None
            )

            extension = Path(path.name).suffix.lower()
            mime_type, _ = mimetypes.guess_type(path.name)

            file_node = SourceNode(
                collection_id=collection.id,
                parent_id=parent_node.id if parent_node else None,
                node_type=SourceNodeType.FILE.value,
                name=path.name,
                relative_path=relative_path,
                depth=len(path.parts) - 1,
                sort_order=sort_order,
                status=SourceNodeStatus.PENDING.value,
                mime_type=mime_type,
                extension=extension or None,
            )

            if self._should_ignore(relative_path):
                file_node.status = SourceNodeStatus.SKIPPED.value
                file_node.error_message = "기본 제외 경로 또는 파일입니다."
                self.repository.add_node(file_node)

                skipped_count += 1
                manifest_files.append(
                    self._manifest_item(file_node)
                )
                continue

            if extension not in ALLOWED_SOURCE_EXTENSIONS:
                file_node.status = SourceNodeStatus.SKIPPED.value
                file_node.error_message = (
                    f"지원하지 않는 확장자입니다: {extension or '(없음)'}"
                )
                self.repository.add_node(file_node)

                skipped_count += 1
                manifest_files.append(
                    self._manifest_item(file_node)
                )
                continue

            destination = safe_join(files_root, relative_path)

            try:
                size_bytes, sha256 = await save_upload_file(
                    upload,
                    destination,
                    max_bytes=MAX_SINGLE_FILE_BYTES,
                )

                total_size += size_bytes

                if total_size > MAX_DIRECTORY_TOTAL_BYTES:
                    destination.unlink(missing_ok=True)
                    raise ValueError(
                        "폴더 전체 용량이 제한을 초과했습니다."
                    )

                file_node.size_bytes = size_bytes
                file_node.sha256 = sha256
                file_node.status = SourceNodeStatus.UPLOADED.value

                self.repository.add_node(file_node)
                uploaded_count += 1

            except Exception as exc:
                file_node.status = SourceNodeStatus.FAILED.value
                file_node.error_message = str(exc)

                self.repository.add_node(file_node)
                failed_count += 1
                warnings.append(
                    f"{relative_path}: {exc}"
                )

            manifest_files.append(
                self._manifest_item(file_node)
            )

        collection.total_files = len(normalized_items)
        collection.supported_files = uploaded_count
        collection.skipped_files = skipped_count
        collection.failed_files = failed_count
        collection.total_size_bytes = total_size

        if failed_count > 0 and uploaded_count > 0:
            collection.status = (
                SourceCollectionStatus.PARTIAL_FAILED.value
            )
        elif failed_count > 0 and uploaded_count == 0:
            collection.status = SourceCollectionStatus.FAILED.value
        else:
            collection.status = SourceCollectionStatus.UPLOADED.value

        collection.metadata_json = json_dumps(
            {
                "root_name": root_name,
                "file_count": len(normalized_items),
            }
        )

        collection = self.repository.save_collection(collection)

        self._write_manifest(
            manifest_path=manifest_path,
            collection=collection,
            files=manifest_files,
        )

        return DirectoryUploadSummary(
            collection=collection,
            uploaded_files=uploaded_count,
            skipped_files=skipped_count,
            failed_files=failed_count,
            warnings=warnings,
        )

    def _validate_request(
        self,
        files: list[UploadFile],
        relative_paths: list[str],
    ) -> None:
        if not files:
            raise ValueError("업로드할 파일이 없습니다.")

        if len(files) != len(relative_paths):
            raise ValueError(
                "files와 relative_paths의 개수가 일치하지 않습니다."
            )

        if len(files) > MAX_DIRECTORY_FILES:
            raise ValueError(
                f"한 번에 최대 {MAX_DIRECTORY_FILES}개 파일까지 "
                "업로드할 수 있습니다."
            )

    def _normalize_upload_items(
        self,
        files: list[UploadFile],
        relative_paths: list[str],
    ) -> list[tuple[UploadFile, str]]:
        normalized: list[tuple[UploadFile, str]] = []
        seen_paths: set[str] = set()

        for upload, raw_path in zip(
            files,
            relative_paths,
            strict=True,
        ):
            relative_path = normalize_relative_path(raw_path)

            if relative_path in seen_paths:
                raise ValueError(
                    f"중복된 상대 경로가 있습니다: {relative_path}"
                )

            seen_paths.add(relative_path)
            normalized.append((upload, relative_path))

        return normalized

    def _build_directory_nodes(
        self,
        *,
        collection_id: str,
        relative_paths: list[str],
    ) -> list[SourceNode]:
        directory_paths: set[str] = set()

        for relative_path in relative_paths:
            path = PurePosixPath(relative_path)

            current_parts: list[str] = []

            for part in path.parts[:-1]:
                current_parts.append(part)
                directory_paths.add(
                    PurePosixPath(*current_parts).as_posix()
                )

        ordered_paths = sorted(
            directory_paths,
            key=lambda value: (
                len(PurePosixPath(value).parts),
                value,
            ),
        )

        created: dict[str, SourceNode] = {}
        nodes: list[SourceNode] = []

        for sort_order, directory_path in enumerate(ordered_paths):
            path = PurePosixPath(directory_path)
            parent_path = (
                path.parent.as_posix()
                if path.parent.as_posix() != "."
                else None
            )

            parent_node = (
                created.get(parent_path)
                if parent_path
                else None
            )

            node = SourceNode(
                collection_id=collection_id,
                parent_id=parent_node.id if parent_node else None,
                node_type=SourceNodeType.DIRECTORY.value,
                name=path.name,
                relative_path=directory_path,
                depth=len(path.parts) - 1,
                sort_order=sort_order,
                status=SourceNodeStatus.READY.value,
            )

            created[directory_path] = node
            nodes.append(node)

        return nodes

    def _should_ignore(self, relative_path: str) -> bool:
        path = PurePosixPath(relative_path)

        if path.name in IGNORED_FILE_NAMES:
            return True

        return any(
            part in IGNORED_DIRECTORY_NAMES
            for part in path.parts
        )

    def _manifest_item(
        self,
        node: SourceNode,
    ) -> dict:
        return {
            "node_id": node.id,
            "relative_path": node.relative_path,
            "name": node.name,
            "status": node.status,
            "size_bytes": node.size_bytes,
            "sha256": node.sha256,
            "document_id": node.document_id,
            "error_message": node.error_message,
        }

    def _write_manifest(
        self,
        *,
        manifest_path: Path,
        collection: SourceCollection,
        files: list[dict],
    ) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        manifest = {
            "collection_id": collection.id,
            "name": collection.name,
            "root_name": collection.root_name,
            "status": collection.status,
            "created_at": collection.created_at.isoformat(),
            "updated_at": collection.updated_at.isoformat(),
            "total_files": collection.total_files,
            "supported_files": collection.supported_files,
            "skipped_files": collection.skipped_files,
            "failed_files": collection.failed_files,
            "total_size_bytes": collection.total_size_bytes,
            "files": files,
        }

        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
