from __future__ import annotations

from sqlmodel import Session, select

from backend.storage.model_utils import utc_now
from backend.storage.models_sources import (
    BookSourceCollection,
    SourceCollection,
    SourceNode,
    UnitSourceLink,
)


class SourceLibraryRepository:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def add_collection(
        self,
        collection: SourceCollection,
    ) -> SourceCollection:
        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)
        return collection

    def get_collection(
        self,
        collection_id: str,
    ) -> SourceCollection | None:
        return self.session.get(SourceCollection, collection_id)

    def list_collections(
        self,
        *,
        include_deleted: bool = False,
    ) -> list[SourceCollection]:
        statement = select(SourceCollection)

        if not include_deleted:
            statement = statement.where(
                SourceCollection.status != "DELETED"
            )

        statement = statement.order_by(
            SourceCollection.created_at.desc()
        )

        return list(self.session.exec(statement).all())

    def save_collection(
        self,
        collection: SourceCollection,
    ) -> SourceCollection:
        collection.updated_at = utc_now()
        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)
        return collection

    # ------------------------------------------------------------------
    # Node
    # ------------------------------------------------------------------

    def add_node(self, node: SourceNode) -> SourceNode:
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    def add_nodes(
        self,
        nodes: list[SourceNode],
    ) -> list[SourceNode]:
        self.session.add_all(nodes)
        self.session.commit()

        for node in nodes:
            self.session.refresh(node)

        return nodes

    def list_nodes(
        self,
        collection_id: str,
    ) -> list[SourceNode]:
        statement = (
            select(SourceNode)
            .where(SourceNode.collection_id == collection_id)
            .order_by(
                SourceNode.depth,
                SourceNode.sort_order,
                SourceNode.relative_path,
            )
        )
        return list(self.session.exec(statement).all())

    def get_node_by_path(
        self,
        collection_id: str,
        relative_path: str,
    ) -> SourceNode | None:
        statement = select(SourceNode).where(
            SourceNode.collection_id == collection_id,
            SourceNode.relative_path == relative_path,
        )
        return self.session.exec(statement).first()

    def save_node(self, node: SourceNode) -> SourceNode:
        node.updated_at = utc_now()
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    # ------------------------------------------------------------------
    # Book ↔ Collection
    # ------------------------------------------------------------------

    def link_collection_to_book(
        self,
        link: BookSourceCollection,
    ) -> BookSourceCollection:
        existing_statement = select(BookSourceCollection).where(
            BookSourceCollection.book_id == link.book_id,
            BookSourceCollection.collection_id == link.collection_id,
        )
        existing = self.session.exec(existing_statement).first()

        if existing:
            existing.enabled = True
            existing.purpose = link.purpose
            existing.priority = link.priority
            existing.updated_at = utc_now()

            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        self.session.add(link)
        self.session.commit()
        self.session.refresh(link)
        return link

    def list_book_collection_links(
        self,
        book_id: str,
        *,
        enabled_only: bool = True,
    ) -> list[BookSourceCollection]:
        statement = select(BookSourceCollection).where(
            BookSourceCollection.book_id == book_id
        )

        if enabled_only:
            statement = statement.where(
                BookSourceCollection.enabled.is_(True)
            )

        statement = statement.order_by(
            BookSourceCollection.priority.desc(),
            BookSourceCollection.created_at,
        )

        return list(self.session.exec(statement).all())

    def unlink_collection_from_book(
        self,
        book_id: str,
        collection_id: str,
    ) -> bool:
        statement = select(BookSourceCollection).where(
            BookSourceCollection.book_id == book_id,
            BookSourceCollection.collection_id == collection_id,
        )
        link = self.session.exec(statement).first()

        if not link:
            return False

        link.enabled = False
        link.updated_at = utc_now()

        self.session.add(link)
        self.session.commit()
        return True

    # ------------------------------------------------------------------
    # Unit ↔ SourceDocument
    # ------------------------------------------------------------------

    def add_unit_source_link(
        self,
        link: UnitSourceLink,
    ) -> UnitSourceLink:
        statement = select(UnitSourceLink).where(
            UnitSourceLink.unit_id == link.unit_id,
            UnitSourceLink.source_document_id
            == link.source_document_id,
        )
        existing = self.session.exec(statement).first()

        if existing:
            existing.enabled = True
            existing.usage_type = link.usage_type
            existing.priority = link.priority
            existing.required = link.required
            existing.assigned_by = link.assigned_by
            existing.assignment_reason = link.assignment_reason
            existing.updated_at = utc_now()

            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        self.session.add(link)
        self.session.commit()
        self.session.refresh(link)
        return link

    def list_unit_source_links(
        self,
        unit_id: str,
        *,
        enabled_only: bool = True,
    ) -> list[UnitSourceLink]:
        statement = select(UnitSourceLink).where(
            UnitSourceLink.unit_id == unit_id
        )

        if enabled_only:
            statement = statement.where(
                UnitSourceLink.enabled.is_(True)
            )

        statement = statement.order_by(
            UnitSourceLink.required.desc(),
            UnitSourceLink.priority.desc(),
            UnitSourceLink.created_at,
        )

        return list(self.session.exec(statement).all())

    def remove_unit_source_link(
        self,
        unit_id: str,
        source_document_id: str,
    ) -> bool:
        statement = select(UnitSourceLink).where(
            UnitSourceLink.unit_id == unit_id,
            UnitSourceLink.source_document_id == source_document_id,
        )
        link = self.session.exec(statement).first()

        if not link:
            return False

        link.enabled = False
        link.updated_at = utc_now()

        self.session.add(link)
        self.session.commit()
        return True


class SourceRepository:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # SourceDocument
    # ------------------------------------------------------------------

    def add_document(
        self,
        document,
    ):
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get_document(
        self,
        source_id: str,
    ):
        from backend.storage.models import SourceDocument

        return self.session.get(
            SourceDocument,
            source_id,
        )

    def list_documents_for_book(
        self,
        book_id: str,
    ):
        from backend.storage.models import SourceDocument

        statement = (
            select(SourceDocument)
            .where(SourceDocument.book_id == book_id)
        )

        return list(
            self.session.exec(statement).all()
        )

    def save_document(
        self,
        document,
    ):
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    # ------------------------------------------------------------------
    # SourceProfile
    # ------------------------------------------------------------------

    def add_profile(
        self,
        profile,
    ):
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get_profile_by_source_id(
        self,
        source_id: str,
    ):
        from backend.storage.models import SourceProfile

        statement = select(SourceProfile).where(
            SourceProfile.source_id == source_id
        )

        return self.session.exec(statement).first()

    def save_profile(
        self,
        profile,
    ):
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    # ------------------------------------------------------------------
    # SourceCollection / SourceNode
    # ------------------------------------------------------------------

    def get_collection(
        self,
        collection_id: str,
    ) -> SourceCollection | None:
        return self.session.get(
            SourceCollection,
            collection_id,
        )

    def list_collection_nodes(
        self,
        collection_id: str,
    ) -> list[SourceNode]:
        statement = (
            select(SourceNode)
            .where(
                SourceNode.collection_id == collection_id
            )
            .order_by(
                SourceNode.depth,
                SourceNode.relative_path,
            )
        )

        return list(
            self.session.exec(statement).all()
        )

    def list_collection_file_nodes(
        self,
        collection_id: str,
    ) -> list[SourceNode]:
        statement = (
            select(SourceNode)
            .where(
                SourceNode.collection_id == collection_id,
                SourceNode.node_type == "FILE",
            )
            .order_by(SourceNode.relative_path)
        )

        return list(
            self.session.exec(statement).all()
        )

    def save_node(
        self,
        node: SourceNode,
    ) -> SourceNode:
        node.updated_at = utc_now()

        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    def save_collection(
        self,
        collection: SourceCollection,
    ) -> SourceCollection:
        collection.updated_at = utc_now()

        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)
        return collection

    # ------------------------------------------------------------------
    # Book ↔ SourceCollection
    # ------------------------------------------------------------------

    def list_collection_links_for_book(
        self,
        book_id: str,
    ) -> list[BookSourceCollection]:
        statement = (
            select(BookSourceCollection)
            .where(
                BookSourceCollection.book_id == book_id,
                BookSourceCollection.enabled.is_(True),
            )
            .order_by(
                BookSourceCollection.priority.desc(),
                BookSourceCollection.created_at,
            )
        )

        return list(
            self.session.exec(statement).all()
        )

    def list_collections_for_book(
        self,
        book_id: str,
    ) -> list[SourceCollection]:
        links = self.list_collection_links_for_book(
            book_id
        )

        collections: list[SourceCollection] = []

        for link in links:
            collection = self.get_collection(
                link.collection_id
            )

            if collection:
                collections.append(collection)

        return collections

    def list_documents_for_collection(
        self,
        collection_id: str,
    ):
        from backend.storage.models import SourceDocument

        nodes = self.list_collection_file_nodes(
            collection_id
        )

        documents: list[SourceDocument] = []

        for node in nodes:
            if not node.document_id:
                continue

            document = self.get_document(node.document_id)

            if document:
                documents.append(document)

        return documents

    # ------------------------------------------------------------------
    # BookUnit ↔ SourceDocument
    # ------------------------------------------------------------------

    def list_unit_source_links(
        self,
        unit_id: str,
    ) -> list[UnitSourceLink]:
        statement = (
            select(UnitSourceLink)
            .where(
                UnitSourceLink.unit_id == unit_id,
                UnitSourceLink.enabled.is_(True),
            )
            .order_by(
                UnitSourceLink.required.desc(),
                UnitSourceLink.priority.desc(),
            )
        )

        return list(
            self.session.exec(statement).all()
        )

    def list_documents_for_unit(
        self,
        unit_id: str,
    ):
        links = self.list_unit_source_links(unit_id)

        result = []

        for link in links:
            document = self.get_document(
                link.source_document_id
            )

            if document:
                result.append((link, document))

        return result
