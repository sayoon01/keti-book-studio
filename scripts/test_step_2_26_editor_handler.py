from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.generation.handlers.editor_handler import (
    EditorHandler,
)
from backend.generation.model_router import (
    GenerationRole,
)


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
    model: str = "fake-editor-model"
    temperature: float = 0.3
    num_predict: int = 512
    num_ctx: int = 4096
    timeout_seconds: float = 30.0
    response_format: str = "markdown"
    enabled: bool = True


class FakeModelRouter:
    def get_config(
        self,
        role: GenerationRole,
    ) -> FakeRoleModelConfig:
        assert role == GenerationRole.EDITOR

        return FakeRoleModelConfig()


class FakeOllamaClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_text(
        self,
        **kwargs: Any,
    ) -> FakeTextResult:
        self.call_count += 1

        return FakeTextResult(
            text=(
                "AI Agent는 목표를 달성하기 위해 "
                "모델과 도구를 활용하는 시스템입니다."
            ),
            metadata=FakeMetadata(
                model="fake-editor-model",
                attempts=1,
                latency_seconds=0.01,
                done_reason="stop",
                prompt_eval_count=20,
                eval_count=30,
            ),
        )


async def main() -> None:
    markdown = """
# AI Agent 기본 개념

## 정의

AI Agent는 모든 문제를 해결하는 프로그램이다.

## 구성요소

Agent는 모델과 도구를 사용할 수 있다.
""".strip()

    selected_text = (
        "AI Agent는 모든 문제를 해결하는 프로그램이다."
    )

    start = markdown.index(selected_text)
    end = start + len(selected_text)

    client = FakeOllamaClient()

    handler = EditorHandler(
        client=client,  # type: ignore[arg-type]
        model_router=FakeModelRouter(),  # type: ignore[arg-type]
        max_attempts=2,
    )

    result = await handler.run(
        book_config={
            "title": "AI Agent 교재",
            "language": "ko",
        },
        chapter_plan={
            "chapter_id": "chapter-editor-test",
            "title": "AI Agent 기본 개념",
            "key_points": [
                "Agent 정의",
                "도구 활용",
            ],
        },
        chapter_draft={
            "artifact_type": "CHAPTER_DRAFT",
            "chapter_id": "chapter-editor-test",
            "title": "AI Agent 기본 개념",
            "summary": "AI Agent를 설명한다.",
            "markdown": markdown,
            "key_points": [
                "Agent 정의",
                "도구 활용",
            ],
            "source_ids": [],
            "metadata": {
                "role": "reviser",
                "revision": 1,
            },
        },
        editor_command={
            "mode": "rewrite",
            "scope": "selection",
            "instruction": (
                "과장되지 않게 수정하세요."
            ),
            "selection": {
                "start": start,
                "end": end,
                "text": selected_text,
            },
        },
        revision_number=2,
    )

    assert client.call_count == 1

    assert result["artifact_type"] == (
        "CHAPTER_DRAFT"
    )

    assert result["chapter_id"] == (
        "chapter-editor-test"
    )

    assert selected_text not in result["markdown"]

    assert (
        "AI Agent는 목표를 달성하기 위해 "
        "모델과 도구를 활용하는 시스템입니다."
        in result["markdown"]
    )

    assert "# AI Agent 기본 개념" in (
        result["markdown"]
    )

    metadata = result["metadata"]

    assert metadata["role"] == "editor"
    assert metadata["stage"] == "editor"
    assert metadata["revision"] == 2
    assert metadata["edit_mode"] == "rewrite"
    assert metadata["edit_scope"] == "selection"

    print("=" * 72)
    print("EDITOR HANDLER TEST")
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
        "revision=",
        metadata["revision"],
    )
    print(
        "edit_mode=",
        metadata["edit_mode"],
    )
    print(
        "edit_scope=",
        metadata["edit_scope"],
    )
    print(
        "markdown_length=",
        len(result["markdown"]),
    )
    print(
        "client_calls=",
        client.call_count,
    )
    print()
    print("PASS: Editor model routing")
    print("PASS: Selection replacement")
    print("PASS: Original chapter preservation")
    print("PASS: CHAPTER_DRAFT construction")
    print("PASS: Editor metadata")


if __name__ == "__main__":
    asyncio.run(main())
