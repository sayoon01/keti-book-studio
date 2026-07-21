from __future__ import annotations

from sqlmodel import Session

from backend.api.schemas.source_library import SourceTreeNode
from backend.services.source_ingestion_service import (
    SourceIngestionResult,
    SourceIngestionService,
)
from backend.services.source_profile_service import (
    SourceProfileService,
)
from backend.storage.repositories.source_repository import (
    SourceLibraryRepository,
)
from backend.storage.models_sources import SourceNode


class SourceLibraryService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SourceLibraryRepository(session)

    def build_collection_tree(
        self,
        collection_id: str,
    ) -> list[SourceTreeNode]:
        nodes = self.repository.list_nodes(collection_id)

        tree_nodes: dict[str, SourceTreeNode] = {
            node.id: self._to_tree_node(node)
            for node in nodes
        }

        roots: list[SourceTreeNode] = []

        for node in nodes:
            current = tree_nodes[node.id]

            if node.parent_id and node.parent_id in tree_nodes:
                tree_nodes[node.parent_id].children.append(current)
            else:
                roots.append(current)

        self._sort_tree(roots)
        return roots

    def analyze_collection(
        self,
        *,
        collection_id: str,
        workspace_id: str,
        book_id: str | None = None,
    ) -> SourceIngestionResult:
        ingestion_service = SourceIngestionService(
            self.session
        )

        result = ingestion_service.ingest_collection(
            collection_id=collection_id,
            workspace_id=workspace_id,
            book_id=book_id,
        )

        profile_service = SourceProfileService(
            self.session
        )

        profile_service.create_profiles_for_collection(
            collection_id
        )

        return result

    def _to_tree_node(
        self,
        node: SourceNode,
    ) -> SourceTreeNode:
        return SourceTreeNode(
            id=node.id,
            node_type=node.node_type,
            name=node.name,
            relative_path=node.relative_path,
            status=node.status,
            document_id=node.document_id,
            size_bytes=node.size_bytes,
            extension=node.extension,
            error_message=node.error_message,
            children=[],
        )

    def _sort_tree(
        self,
        nodes: list[SourceTreeNode],
    ) -> None:
        nodes.sort(
            key=lambda node: (
                0 if node.node_type == "DIRECTORY" else 1,
                node.name.lower(),
            )
        )

        for node in nodes:
            self._sort_tree(node.children)
