from __future__ import annotations

from sqlmodel import Session, select

from backend.storage.models import (
    BookConfig,
    BookOutline,
    BookProject,
    BookUnit,
    SourceDocument,
    SourceProfile,
)
from backend.storage.models_sources import (
    BookSourceCollection,
    SourceNode,
    UnitSourceLink,
)


class WorkspaceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_book(
        self,
        book_id: str,
    ) -> BookProject | None:
        return self.session.get(
            BookProject,
            book_id,
        )

    def get_book_config(
        self,
        book_id: str,
    ) -> BookConfig | None:
        statement = select(BookConfig).where(
            BookConfig.book_id == book_id
        )

        return self.session.exec(statement).first()

    def get_unit(
        self,
        unit_id: str,
    ) -> BookUnit | None:
        return self.session.get(
            BookUnit,
            unit_id,
        )

    def get_unit_for_book(
        self,
        unit_id: str,
        book_id: str,
    ) -> BookUnit | None:
        unit = self.get_unit(unit_id)

        if not unit:
            return None

        outline = self.session.get(
            BookOutline,
            unit.outline_id,
        )

        if not outline or outline.book_id != book_id:
            return None

        return unit

    def list_units(
        self,
        book_id: str,
    ) -> list[BookUnit]:
        statement = (
            select(BookUnit)
            .join(
                BookOutline,
                BookUnit.outline_id == BookOutline.outline_id,
            )
            .where(BookOutline.book_id == book_id)
            .order_by(BookUnit.order)
        )

        return list(
            self.session.exec(statement).all()
        )

    def get_source_document(
        self,
        source_id: str,
    ) -> SourceDocument | None:
        return self.session.get(
            SourceDocument,
            source_id,
        )

    def get_source_profile(
        self,
        source_id: str,
    ) -> SourceProfile | None:
        statement = select(SourceProfile).where(
            SourceProfile.source_id == source_id
        )

        return self.session.exec(statement).first()

    def get_source_node_by_document_id(
        self,
        source_id: str,
    ) -> SourceNode | None:
        statement = select(SourceNode).where(
            SourceNode.document_id == source_id
        )

        return self.session.exec(statement).first()

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

    def list_book_collection_links(
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
                BookSourceCollection.priority.desc()
            )
        )

        return list(
            self.session.exec(statement).all()
        )

    def list_documents_from_book_collections(
        self,
        book_id: str,
    ) -> list[SourceDocument]:
        links = self.list_book_collection_links(book_id)

        result: list[SourceDocument] = []
        seen: set[str] = set()

        for link in links:
            node_statement = select(SourceNode).where(
                SourceNode.collection_id
                == link.collection_id,
                SourceNode.document_id.is_not(None),
            )

            nodes = list(
                self.session.exec(node_statement).all()
            )

            for node in nodes:
                if (
                    not node.document_id
                    or node.document_id in seen
                ):
                    continue

                document = self.get_source_document(
                    node.document_id
                )

                if document:
                    seen.add(document.source_id)
                    result.append(document)

        return result
