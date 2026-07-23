"""
Deprecated compatibility module.

새 코드는 backend.generation.chapter_generation_service를 사용하세요.
"""

from backend.generation.chapter_generation_service import (  # noqa: F401
    ChapterGenerationService,
    ChapterLlmService,
)

__all__ = [
    "ChapterGenerationService",
    "ChapterLlmService",
]
