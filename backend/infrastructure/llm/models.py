from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    base_url: str
    timeout_seconds: float
    max_retries: int
    retry_delay_seconds: float
    keep_alive: str

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        return cls(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ).rstrip("/"),
            timeout_seconds=float(
                os.getenv(
                    "OLLAMA_TIMEOUT_SECONDS",
                    "600",
                )
            ),
            max_retries=int(
                os.getenv(
                    "OLLAMA_MAX_RETRIES",
                    "1",
                )
            ),
            retry_delay_seconds=float(
                os.getenv(
                    "OLLAMA_RETRY_DELAY_SECONDS",
                    "2",
                )
            ),
            keep_alive=os.getenv(
                "OLLAMA_KEEP_ALIVE",
                "5m",
            ),
        )


@dataclass(frozen=True, slots=True)
class OllamaGenerationMetadata:
    model: str
    attempts: int
    latency_seconds: float
    done_reason: str | None
    prompt_eval_count: int | None
    eval_count: int | None


@dataclass(frozen=True, slots=True)
class OllamaTextResult:
    text: str
    metadata: OllamaGenerationMetadata


@dataclass(frozen=True, slots=True)
class OllamaJsonResult:
    data: dict[str, Any]
    metadata: OllamaGenerationMetadata
