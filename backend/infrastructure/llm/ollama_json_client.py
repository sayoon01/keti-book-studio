"""
Deprecated compatibility module.

새 코드는 backend.infrastructure.llm.OllamaClient를 사용하세요.
"""

from backend.infrastructure.llm.exceptions import (
    OllamaClientError,
    OllamaIncompleteResponseError,
    OllamaLowQualityResponseError,
    OllamaModelNotFoundError,
    OllamaResponseParseError,
)
from backend.infrastructure.llm.models import (
    OllamaGenerationMetadata,
    OllamaJsonResult,
    OllamaSettings,
    OllamaTextResult,
)
from backend.infrastructure.llm.ollama_client import (
    OllamaClient,
)

# 이전 이름 호환
OllamaJsonClient = OllamaClient

__all__ = [
    "OllamaClient",
    "OllamaClientError",
    "OllamaGenerationMetadata",
    "OllamaIncompleteResponseError",
    "OllamaJsonClient",
    "OllamaJsonResult",
    "OllamaLowQualityResponseError",
    "OllamaModelNotFoundError",
    "OllamaResponseParseError",
    "OllamaSettings",
    "OllamaTextResult",
]
