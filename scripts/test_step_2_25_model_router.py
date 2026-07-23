from __future__ import annotations

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
    config = router.get_config(
        GenerationRole.WRITER
    )

    print("=== Writer Model Config ===")
    print(f"role={config.role.value}")
    print(f"model={config.model}")
    print(
        f"temperature={config.temperature}"
    )
    print(
        f"timeout_seconds={config.timeout_seconds}"
    )
    print(
        f"num_predict={config.num_predict}"
    )

    assert config.model == "gemma4:31b", (
        "Writer 모델이 gemma4:31b가 아닙니다. "
        f"actual={config.model!r}"
    )

    print("\nPASS: ModelRouter Writer 설정 정상")


if __name__ == "__main__":
    main()
