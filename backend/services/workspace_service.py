from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from backend.publishing.schemas import (
    PublishingWorkspace,
    WorkspaceBookConfig,
    WorkspaceSource,
    WorkspaceUnit,
)
from backend.storage.repositories.workspace_repository import (
    WorkspaceRepository,
)


class WorkspaceService:
    """
    Shared Blackboard를 생성하는 서비스입니다.

    Agent는 DB를 직접 읽지 않고,
    이 서비스가 만든 역할별 Workspace View만 사용합니다.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = WorkspaceRepository(session)

    def build_workspace(
        self,
        *,
        book_id: str,
        unit_id: str | None = None,
        include_full_text: bool = False,
    ) -> PublishingWorkspace:
        book = self.repository.get_book(book_id)

        if not book:
            raise ValueError(
                "BookProject를 찾을 수 없습니다."
            )

        config = self.repository.get_book_config(
            book_id
        )

        automation_level = (
            self._resolve_automation_level(config)
        )

        workspace_book = self._build_book_config(
            book=book,
            config=config,
            automation_level=automation_level,
        )

        workspace_unit = None

        if unit_id:
            unit = self.repository.get_unit_for_book(
                unit_id,
                book_id,
            )

            if not unit:
                raise ValueError(
                    "BookUnit을 찾을 수 없거나 "
                    "해당 책에 속하지 않습니다."
                )

            workspace_unit = self._build_unit(unit)

        sources = self._build_sources(
            book_id=book_id,
            unit_id=unit_id,
            include_full_text=include_full_text,
        )

        return PublishingWorkspace(
            book=workspace_book,
            unit=workspace_unit,
            sources=sources,
            artifacts=[],
            review_issues=[],
            decisions=[],
            previous_unit_summaries=[],
            book_policy=self._build_book_policy(
                config,
                automation_level=automation_level,
            ),
            role_persona={},
            runtime_state={
                "source_count": len(sources),
                "include_full_text": include_full_text,
            },
        )

    def _build_book_config(
        self,
        *,
        book,
        config,
        automation_level: str,
    ) -> WorkspaceBookConfig:
        return WorkspaceBookConfig(
            book_id=book.book_id,
            title=self._first_value(
                book,
                ["title", "name"],
                default="제목 없음",
            ),
            document_type=self._first_value(
                config,
                [
                    "document_type",
                    "book_type",
                    "type",
                ],
            ),
            target_reader=self._first_value(
                config,
                [
                    "target_reader",
                    "reader",
                    "audience",
                ],
            ),
            purpose=self._first_value(
                config,
                [
                    "purpose",
                    "goal",
                    "description",
                ],
            ),
            language=self._first_value(
                config,
                ["language"],
                default="ko",
            ),
            automation_level=automation_level,
            workflow_type=self._first_value(
                config,
                ["workflow_type"],
                default="technical_book",
            ),
            metadata={},
        )

    def _build_unit(
        self,
        unit,
    ) -> WorkspaceUnit:
        return WorkspaceUnit(
            unit_id=unit.unit_id,
            title=self._first_value(
                unit,
                ["title", "name"],
                default="제목 없음",
            ),
            description=self._first_value(
                unit,
                ["description", "summary"],
            ),
            order_index=int(
                self._first_value(
                    unit,
                    [
                        "order",
                        "order_index",
                        "position",
                        "sort_order",
                    ],
                    default=0,
                )
                or 0
            ),
            status=self._first_value(
                unit,
                ["status"],
            ),
            target_characters=self._to_optional_int(
                self._first_value(
                    unit,
                    [
                        "target_characters",
                        "target_length",
                        "target_chars",
                    ],
                )
            ),
            is_important=bool(
                self._first_value(
                    unit,
                    [
                        "is_important",
                        "important",
                    ],
                    default=False,
                )
            ),
            metadata={},
        )

    def _build_sources(
        self,
        *,
        book_id: str,
        unit_id: str | None,
        include_full_text: bool,
    ) -> list[WorkspaceSource]:
        if unit_id:
            links = (
                self.repository.list_unit_source_links(
                    unit_id
                )
            )

            result: list[WorkspaceSource] = []

            for link in links:
                document = (
                    self.repository.get_source_document(
                        link.source_document_id
                    )
                )

                if not document:
                    continue

                result.append(
                    self._build_workspace_source(
                        document=document,
                        usage_type=link.usage_type,
                        priority=link.priority,
                        required=link.required,
                        include_full_text=include_full_text,
                    )
                )

            if result:
                return result

        documents = (
            self.repository
            .list_documents_from_book_collections(
                book_id
            )
        )

        return [
            self._build_workspace_source(
                document=document,
                usage_type="REFERENCE",
                priority=0,
                required=False,
                include_full_text=include_full_text,
            )
            for document in documents
        ]

    def _build_workspace_source(
        self,
        *,
        document,
        usage_type: str,
        priority: int,
        required: bool,
        include_full_text: bool,
    ) -> WorkspaceSource:
        profile = (
            self.repository.get_source_profile(
                document.source_id
            )
        )

        node = (
            self.repository
            .get_source_node_by_document_id(
                document.source_id
            )
        )

        profile_keywords: list[str] = []

        if profile and profile.main_topics:
            profile_keywords = list(profile.main_topics)

        extracted_text = None

        if include_full_text:
            extracted_text = self._first_value(
                document,
                [
                    "raw_text",
                    "extracted_text",
                    "content",
                    "text",
                ],
            )

        summary = self._first_value(
            profile,
            [
                "summary",
                "description",
            ],
        )

        return WorkspaceSource(
            source_id=document.source_id,
            title=self._first_value(
                document,
                ["title", "name"],
                default=document.source_id,
            ),
            source_type=self._first_value(
                document,
                ["source_type", "type"],
                default="unknown",
            ),
            collection_id=(
                node.collection_id if node else None
            ),
            node_id=node.id if node else None,
            relative_path=(
                node.relative_path if node else None
            ),
            usage_type=usage_type,
            priority=priority,
            required=required,
            summary=summary,
            keywords=profile_keywords,
            extracted_text=extracted_text,
            metadata={},
        )

    def _build_book_policy(
        self,
        config,
        *,
        automation_level: str,
    ) -> dict[str, Any]:
        return {
            "automation_level": automation_level,
            "reader_test_policy": (
                "IMPORTANT_OR_FINAL"
            ),
            "review_round_limit": 2,
            "research_request_limit": 2,
            "editorial_loop_limit": 3,
            "agent_communication": (
                "BLACKBOARD_ARTIFACT_MESSAGE"
            ),
        }

    def _resolve_automation_level(
        self,
        config: object | None,
    ) -> str:
        raw_value = self._first_value(
            config,
            ["approval_mode", "automation_level"],
            default="BALANCED",
        )

        return self._normalize_automation_level(
            raw_value,
        )

    @staticmethod
    def _normalize_automation_level(
        value: str | None,
    ) -> str:
        normalized = (
            value or "BALANCED"
        ).strip().upper()

        aliases = {
            "AUTO": "AUTO",
            "AUTOMATIC": "AUTO",
            "BALANCED": "BALANCED",
            "SEMI_AUTO": "BALANCED",
            "MANUAL": "MANUAL",
        }

        return aliases.get(
            normalized,
            "BALANCED",
        )

    def _first_value(
        self,
        obj,
        field_names: list[str],
        default: Any = None,
    ) -> Any:
        if obj is None:
            return default

        for field_name in field_names:
            value = getattr(obj, field_name, None)

            if value is not None:
                return value

        return default

    def _read_json_list(
        self,
        raw: str | None,
    ) -> list[str]:
        if not raw:
            return []

        try:
            value = json.loads(raw)

            if isinstance(value, list):
                return [
                    str(item)
                    for item in value
                ]

        except json.JSONDecodeError:
            pass

        return []

    def _to_optional_int(
        self,
        value: Any,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
