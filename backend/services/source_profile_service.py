from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlmodel import Session

from backend.storage.models import (
    SourceDocument,
    SourceProfile,
)
from backend.storage.repositories.source_repository import (
    SourceRepository,
)


class SourceProfileService:
    """
    초기 버전은 코드 기반 프로파일을 생성합니다.

    다음 단계에서 Research Agent 또는 LLM을 붙여
    주제·요약·책 적합성 분석을 확장할 수 있습니다.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = SourceRepository(session)

    def create_or_update_profile(
        self,
        source_id: str,
    ) -> SourceProfile:
        document = self.repository.get_document(
            source_id
        )

        if not document:
            raise ValueError(
                "SourceDocument를 찾을 수 없습니다."
            )

        text = self._get_document_text(document)

        summary = self._build_summary(text)
        keywords = self._extract_keywords(text)

        profile = (
            self.repository.get_profile_by_source_id(
                source_id
            )
        )

        if profile:
            profile.summary = summary
            profile.main_topics = keywords
            profile.analysis_purpose = "rule_based_profile"
            return self.repository.save_profile(profile)

        return self.repository.add_profile(
            SourceProfile(
                source_id=document.source_id,
                summary=summary,
                main_topics=keywords,
                analysis_purpose="rule_based_profile",
            )
        )

    def create_profiles_for_collection(
        self,
        collection_id: str,
    ) -> list[SourceProfile]:
        documents = (
            self.repository.list_documents_for_collection(
                collection_id
            )
        )

        profiles: list[SourceProfile] = []

        for document in documents:
            profiles.append(
                self.create_or_update_profile(
                    document.source_id
                )
            )

        return profiles

    def _get_document_text(
        self,
        document: SourceDocument,
    ) -> str:
        candidates = [
            "raw_text",
            "extracted_text",
            "content",
            "text",
        ]

        for name in candidates:
            value = getattr(document, name, None)

            if isinstance(value, str) and value.strip():
                return value

        return ""

    def _build_summary(
        self,
        text: str,
        maximum_length: int = 800,
    ) -> str:
        normalized = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        if len(normalized) <= maximum_length:
            return normalized

        return normalized[:maximum_length].rstrip() + "..."

    def _extract_keywords(
        self,
        text: str,
        limit: int = 20,
    ) -> list[str]:
        tokens = re.findall(
            r"[가-힣A-Za-z][가-힣A-Za-z0-9_-]{1,}",
            text,
        )

        stopwords = {
            "그리고",
            "그러나",
            "대한",
            "통해",
            "에서",
            "으로",
            "하는",
            "한다",
            "있다",
            "있는",
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
        }

        counter = Counter(
            token.lower()
            for token in tokens
            if token.lower() not in stopwords
        )

        return [
            token
            for token, _ in counter.most_common(limit)
        ]

    def _detect_language(
        self,
        text: str,
    ) -> str:
        korean_count = len(
            re.findall(r"[가-힣]", text)
        )
        english_count = len(
            re.findall(r"[A-Za-z]", text)
        )

        if korean_count > english_count:
            return "ko"

        if english_count > korean_count:
            return "en"

        return "unknown"
