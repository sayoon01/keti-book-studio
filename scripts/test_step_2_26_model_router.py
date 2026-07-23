from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)


def main() -> None:
    load_dotenv()

    router = ModelRouter()

    print("=" * 70)
    print("STEP 2-26 MODEL ROUTER")
    print("=" * 70)

    print(
        json.dumps(
            router.as_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("=" * 70)
    print("ROLE CHECK")
    print("=" * 70)

    expected_models = {
        GenerationRole.RESEARCHER: "qwen3:32b",
        GenerationRole.PLANNER: "qwen3:32b",
        GenerationRole.WRITER: "gemma4:31b",
        GenerationRole.REVIEWER: "qwen3:32b",
        GenerationRole.TECHNICAL_REVIEWER: (
            "qwen3-coder:30b"
        ),
        GenerationRole.EDITOR: "qwen3:32b",
        GenerationRole.REVISER: "gemma4:31b",
        GenerationRole.READER: "qwen3:32b",
    }

    for role, expected_model in expected_models.items():
        config = router.get_config(role)

        print(
            f"{role.value:<22} "
            f"model={config.model:<20} "
            f"format={config.response_format:<10} "
            f"enabled={config.enabled}"
        )

        assert config.model == expected_model, (
            f"{role.value} 모델이 예상과 다릅니다. "
            f"expected={expected_model}, "
            f"actual={config.model}"
        )

    writer = router.get_config(
        GenerationRole.WRITER
    )

    assert writer.response_format == "markdown"
    assert writer.model == "gemma4:31b"

    researcher = router.get_config(
        GenerationRole.RESEARCHER
    )

    assert researcher.response_format == "json"
    assert researcher.model == "qwen3:32b"

    technical_reviewer = router.get_config(
        GenerationRole.TECHNICAL_REVIEWER
    )

    assert (
        technical_reviewer.model
        == "qwen3-coder:30b"
    )

    print()
    print("=" * 70)
    print("TECHNICAL REVIEW CONDITION")
    print("=" * 70)

    programming_result = (
        router.requires_technical_review(
            book_type="programming"
        )
    )

    normal_result = (
        router.requires_technical_review(
            book_type="novel"
        )
    )

    code_block_result = (
        router.requires_technical_review(
            book_type="education",
            chapter_text=(
                "# Example\n\n"
                "```python\n"
                "print('hello')\n"
                "```"
            ),
        )
    )

    print(
        "programming book:",
        programming_result,
    )
    print(
        "normal novel:",
        normal_result,
    )
    print(
        "chapter with code block:",
        code_block_result,
    )

    assert programming_result is True
    assert normal_result is False
    assert code_block_result is True

    print()
    print("PASS: ModelRouter configuration")
    print("PASS: Writer markdown format")
    print("PASS: Structured roles JSON format")
    print("PASS: Technical Reviewer routing")
    print()
    print("PASS: STEP 2-26-1")


if __name__ == "__main__":
    main()
