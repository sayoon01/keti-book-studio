from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session

from backend.services.source_extraction_service import (
    SourceExtractionService,
    UnsupportedSourceTypeError,
)
from backend.storage.model_utils import (
    json_dumps,
    utc_now,
)
from backend.storage.models import (
    SourceDocument,
)
from backend.storage.models_sources import (
    SourceCollectionStatus,
    SourceNode,
    SourceNodeStatus,
)
from backend.storage.repositories.source_repository import (
    SourceRepository,
)


@dataclass
class SourceIngestionResult:
    collection_id: str
    total_files: int
    completed_files: int
    skipped_files: int
    failed_files: int
    document_ids: list[str]
    warnings: list[str]


class SourceIngestionService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SourceRepository(session)
        self.extractor = SourceExtractionService()

    def ingest_collection(
        self,
        *,
        collection_id: str,
        workspace_id: str,
        book_id: str | None = None,
    ) -> SourceIngestionResult:
        collection = self.repository.get_collection(
            collection_id
        )

        if not collection:
            raise ValueError(
                "자료 컬렉션을 찾을 수 없습니다."
            )

        file_nodes = (
            self.repository.list_collection_file_nodes(
                collection_id
            )
        )

        collection.status = (
            SourceCollectionStatus.ANALYZING.value
        )
        self.repository.save_collection(collection)

        completed = 0
        skipped = 0
        failed = 0

        document_ids: list[str] = []
        warnings: list[str] = []

        for node in file_nodes:
            if node.status == SourceNodeStatus.SKIPPED.value:
                skipped += 1
                continue

            if node.document_id:
                existing = self.repository.get_document(
                    node.document_id
                )

                if existing:
                    completed += 1
                    document_ids.append(existing.source_id)
                    continue

            try:
                document = self._ingest_node(
                    node=node,
                    workspace_id=workspace_id,
                    book_id=book_id,
                )

                completed += 1
                document_ids.append(document.source_id)

            except UnsupportedSourceTypeError as exc:
                skipped += 1

                node.status = SourceNodeStatus.SKIPPED.value
                node.error_message = str(exc)

                self.repository.save_node(node)
                warnings.append(
                    f"{node.relative_path}: {exc}"
                )

            except Exception as exc:
                failed += 1

                node.status = SourceNodeStatus.FAILED.value
                node.error_message = str(exc)

                self.repository.save_node(node)
                warnings.append(
                    f"{node.relative_path}: {exc}"
                )

        collection.supported_files = completed
        collection.skipped_files = skipped
        collection.failed_files = failed

        if failed > 0 and completed > 0:
            collection.status = (
                SourceCollectionStatus.PARTIAL_FAILED.value
            )
        elif failed > 0 and completed == 0:
            collection.status = (
                SourceCollectionStatus.FAILED.value
            )
        else:
            collection.status = (
                SourceCollectionStatus.READY.value
            )

        self.repository.save_collection(collection)

        return SourceIngestionResult(
            collection_id=collection.id,
            total_files=len(file_nodes),
            completed_files=completed,
            skipped_files=skipped,
            failed_files=failed,
            document_ids=document_ids,
            warnings=warnings,
        )

    def _ingest_node(
        self,
        *,
        node: SourceNode,
        workspace_id: str,
        book_id: str | None,
    ) -> SourceDocument:
        collection = self.repository.get_collection(
            node.collection_id
        )

        if not collection:
            raise ValueError(
                "SourceNode의 Collection을 찾을 수 없습니다."
            )

        if not collection.storage_path:
            raise ValueError(
                "Collection 저장 경로가 없습니다."
            )

        collection_root = Path(collection.storage_path)
        file_path = collection_root / "files" / node.relative_path

        node.status = SourceNodeStatus.EXTRACTING.value
        node.error_message = None
        self.repository.save_node(node)

        extracted = self.extractor.extract(file_path)

        document = self._create_source_document(
            node=node,
            extracted=extracted,
            file_path=file_path,
            workspace_id=workspace_id,
            book_id=book_id,
        )

        document = self.repository.add_document(
            document
        )

        node.document_id = document.source_id
        node.status = SourceNodeStatus.READY.value
        node.error_message = None

        metadata = self._load_json(
            node.metadata_json,
            {},
        )

        metadata["ingestion"] = {
            "source_id": document.source_id,
            "character_count": extracted.character_count,
            "ingested_at": utc_now().isoformat(),
        }

        node.metadata_json = json_dumps(metadata)
        self.repository.save_node(node)

        return document

    def _create_source_document(
        self,
        *,
        node: SourceNode,
        extracted,
        file_path: Path,
        workspace_id: str,
        book_id: str | None,
    ) -> SourceDocument:
        model_fields = SourceDocument.model_fields
        values: dict[str, Any] = {}

        candidate_values: dict[str, Any] = {
            "workspace_id": workspace_id,
            "book_id": book_id,
            "source_type": extracted.source_type,
            "title": extracted.title,
            "file_path": str(file_path),
            "raw_text": extracted.text,
            "status": "analyzed",
            "content_hash": node.sha256,
            "created_at": utc_now(),
        }

        for field_name, field_value in candidate_values.items():
            if (
                field_name in model_fields
                and field_value is not None
            ):
                values[field_name] = field_value

        required_missing: list[str] = []

        for field_name, field_info in model_fields.items():
            if field_name in values:
                continue

            if field_name == "source_id":
                continue

            if field_info.is_required():
                required_missing.append(field_name)

        if required_missing:
            raise ValueError(
                "SourceDocument 생성에 필요한 필드를 "
                "자동으로 채우지 못했습니다: "
                + ", ".join(required_missing)
            )

        return SourceDocument(**values)

    def _load_json(
        self,
        raw: str | None,
        default: Any,
    ) -> Any:
        if not raw:
            return default

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
