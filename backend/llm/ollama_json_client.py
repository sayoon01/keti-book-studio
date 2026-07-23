"""
Deprecated compatibility module.

새 코드는 backend.infrastructure.llm.OllamaClient를 사용하세요.
"""

from backend.infrastructure.llm import *  # noqa: F401,F403
from backend.infrastructure.llm.ollama_json_client import (  # noqa: F401
    OllamaJsonClient,
)
