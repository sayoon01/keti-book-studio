from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.handlers.base_text_handler import (
    BaseTextHandler,
    TextExecutionContext,
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
class FakeTextResult:
    text: str
    metadata: FakeMetadata


@dataclass(frozen=True, slots=True)
class FakeRoleModelConfig:
    model: str = "fake-text-model"
    temperature: float = 0.2
    num_predict: int = 256
    num_ctx: int = 2048
    timeout_seconds: float = 30.0
    response_format: str = "text"
    enabled: bool = True


class FakeModelRouter:
    def get_config(
        self,
        role: GenerationRole,
    ) -> FakeRoleModelConfig:
        assert role == GenerationRole.REVISER

        return FakeRoleModelConfig()


class FakeOllamaClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_text(
        self,
        **kwargs: Any,
    ) -> FakeTextResult:
        self.call_count += 1

        assert kwargs["model"] == "fake-text-model"
        assert kwargs["system_prompt"] == "system"
        assert kwargs["user_prompt"] == "user"

        fenced = (
            "```markdown\n"
            "# 수정된 챕터\n"
            "\n"
            "## 개요\n"
            "\n"
            "Reviewer의 수정 지침을 반영한 본문입니다.\n"
            "\n"
            "## 상세 설명\n"
            "\n"
            "이 문단은 BaseTextHandler의 텍스트 추출과\n"
            "Markdown 코드 블록 제거를 확인하기 위한 내용입니다.\n"
            "```"
        )

        return FakeTextResult(
            text=fenced,
            metadata=FakeMetadata(
                model="fake-text-model",
                attempts=1,
                latency_seconds=0.01,
                done_reason="stop",
                prompt_eval_count=10,
                eval_count=30,
            ),
        )


class FakeTextHandler(
    BaseTextHandler[dict[str, Any]]
):
    role = GenerationRole.REVISER
    operation_name = "Fake Text Handler"

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

    def _build_artifact(
        self,
        *,
        generated_text: str,
        execution_context: TextExecutionContext,
        **inputs: Any,
    ) -> dict[str, Any]:
        return {
            "artifact_type": "FAKE_TEXT_ARTIFACT",
            "chapter_id": inputs["chapter_id"],
            "markdown": generated_text,
            "metadata": self._build_metadata(
                execution_context
            ),
        }


async def main() -> None:
    client = FakeOllamaClient()

    handler = FakeTextHandler(
        client=client,  # type: ignore[arg-type]
        model_router=FakeModelRouter(),  # type: ignore[arg-type]
        max_attempts=2,
    )

    result = await handler.run(
        chapter_id="chapter-text-test"
    )

    assert client.call_count == 1

    assert result["artifact_type"] == (
        "FAKE_TEXT_ARTIFACT"
    )

    assert result["chapter_id"] == (
        "chapter-text-test"
    )

    assert result["markdown"].startswith(
        "# 수정된 챕터"
    )

    assert "```markdown" not in result["markdown"]

    assert result["metadata"]["model"] == (
        "fake-text-model"
    )

    assert result["metadata"]["role"] == "reviser"

    print("=" * 72)
    print("BASE TEXT HANDLER TEST")
    print("=" * 72)
    print(
        "artifact_type=",
        result["artifact_type"],
    )
    print(
        "chapter_id=",
        result["chapter_id"],
    )
    print(
        "model=",
        result["metadata"]["model"],
    )
    print(
        "role=",
        result["metadata"]["role"],
    )
    print(
        "markdown_starts_with_h1=",
        result["markdown"].startswith("# "),
    )
    print(
        "client_calls=",
        client.call_count,
    )
    print()
    print("PASS: Text Template Method execution")
    print("PASS: generate_text delegation")
    print("PASS: Text response extraction")
    print("PASS: Markdown fence cleanup")
    print("PASS: Artifact construction")
    print("PASS: Text metadata generation")


if __name__ == "__main__":
    asyncio.run(main())
