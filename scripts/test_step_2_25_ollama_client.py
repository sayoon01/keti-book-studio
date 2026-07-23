from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.infrastructure.llm import (
    OllamaClient,
)


async def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )

    client = OllamaClient()

    result = await client.generate_json(
        model="gemma4:31b",
        temperature=0.2,
        timeout_seconds=600,
        num_predict=1024,
        num_ctx=8192,
        system_prompt=(
            "당신은 JSON 형식만 반환하는 도우미입니다. "
            "설명이나 코드펜스를 붙이지 마세요."
        ),
        user_prompt="""
다음 형식으로 한국어 JSON 객체 하나만 반환하세요.

{
  "status": "ok",
  "message": "Ollama 연결 성공",
  "items": ["첫 번째", "두 번째"]
}
""".strip(),
    )

    print("\n=== DATA ===")
    print(
        json.dumps(
            result.data,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n=== METADATA ===")
    print(result.metadata)

    assert result.data.get("status") == "ok"
    print("\nPASS: OllamaClient 정상")


if __name__ == "__main__":
    asyncio.run(main())
