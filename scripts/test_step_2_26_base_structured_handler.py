from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.handlers.base_structured_handler import (
    BaseStructuredHandler,
    StructuredExecutionContext,
)
from backend.generation.model_router import (
    GenerationRole,
)


@dataclass(frozen=True, slots=True)
class FakePromptBundle:
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True, slots=True)
class FakeMetadata:
    model: str
    attempts: int
    latency_seconds: float
    done_reason: str
    prompt_eval_count: int
    eval_count: int


@dataclass(frozen=True, slots=True)
class FakeGenerationResult:
    data: dict[str, Any]
    metadata: FakeMetadata


@dataclass(frozen=True, slots=True)
class FakeRoleModelConfig:
    model: str = "fake-model"
    temperature: float = 0.1
    num_predict: int = 128
    num_ctx: int = 1024
    timeout_seconds: float = 30.0
    response_format: str = "json"
    enabled: bool = True


class FakeModelRouter:
    def get_config(
        self,
        role: GenerationRole,
    ) -> FakeRoleModelConfig:
        assert role == GenerationRole.RESEARCHER

        return FakeRoleModelConfig()


class FakeOllamaClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_json(
        self,
        **kwargs: Any,
    ) -> FakeGenerationResult:
        self.call_count += 1

        assert kwargs["model"] == "fake-model"
        assert kwargs["system_prompt"] == "system"
        assert kwargs["user_prompt"] == "user"

        return FakeGenerationResult(
            data={
                "chapter_id": "wrong-model-id",
                "title": "Fake title",
                "value": "generated",
            },
            metadata=FakeMetadata(
                model="fake-model",
                attempts=1,
                latency_seconds=0.01,
                done_reason="stop",
                prompt_eval_count=10,
                eval_count=20,
            ),
        )


def fake_validator(
    payload: dict[str, Any],
) -> dict[str, Any]:
    assert payload["chapter_id"] == "chapter-test"
    assert payload["metadata"]["role"] == "researcher"
    assert payload["metadata"]["model"] == "fake-model"

    return {
        "artifact_type": "FAKE_ARTIFACT",
        **payload,
    }


class FakeStructuredHandler(
    BaseStructuredHandler[dict[str, Any]]
):
    role = GenerationRole.RESEARCHER
    operation_name = "Fake Structured Handler"
    validator = staticmethod(fake_validator)

    async def run(
        self,
        *,
        chapter_id: str,
    ) -> dict[str, Any]:
        return await self._execute(
            chapter_id=chapter_id
        )

    def _validate_inputs(
        self,
        **inputs: Any,
    ) -> None:
        if not str(
            inputs.get("chapter_id", "")
        ).strip():
            raise ValueError(
                "chapter_id가 필요합니다."
            )

    def _build_prompts(
        self,
        **inputs: Any,
    ) -> FakePromptBundle:
        return FakePromptBundle(
            system_prompt="system",
            user_prompt="user",
        )

    def _enrich_payload(
        self,
        *,
        payload: dict[str, Any],
        execution_context: StructuredExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        result = dict(payload)

        result["chapter_id"] = inputs["chapter_id"]
        result["metadata"] = self._build_metadata(
            execution_context
        )

        return result


async def main() -> None:
    client = FakeOllamaClient()

    handler = FakeStructuredHandler(
        client=client,  # type: ignore[arg-type]
        model_router=FakeModelRouter(),  # type: ignore[arg-type]
        max_attempts=2,
    )

    result = await handler.run(
        chapter_id="chapter-test"
    )

    assert client.call_count == 1
    assert result["artifact_type"] == "FAKE_ARTIFACT"
    assert result["chapter_id"] == "chapter-test"
    assert result["value"] == "generated"
    assert result["metadata"]["model"] == "fake-model"
    assert result["metadata"]["role"] == "researcher"
    assert result["metadata"]["attempt"] == 1

    print("=" * 72)
    print("BASE STRUCTURED HANDLER TEST")
    print("=" * 72)
    print("artifact_type=", result["artifact_type"])
    print("chapter_id=", result["chapter_id"])
    print("model=", result["metadata"]["model"])
    print("role=", result["metadata"]["role"])
    print("client_calls=", client.call_count)
    print()
    print("PASS: Template Method execution")
    print("PASS: Prompt delegation")
    print("PASS: Payload enrichment")
    print("PASS: Validator delegation")
    print("PASS: Metadata generation")


if __name__ == "__main__":
    asyncio.run(main())
