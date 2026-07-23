from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.llm.ollama_json_client import (
    OllamaClientError,
    OllamaIncompleteResponseError,
    OllamaJsonClient,
    OllamaSettings,
)


def _chat_payload(
    *,
    done: bool,
    content: str,
) -> dict:
    return {
        "done": done,
        "message": {
            "content": content,
        },
    }


@pytest.mark.asyncio
async def test_generate_json_retries_when_done_is_false(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = OllamaSettings(
        base_url="http://127.0.0.1:11434",
        model="test-model",
        timeout_seconds=30,
        temperature=0.3,
        max_retries=1,
        retry_delay_seconds=0,
    )

    client = OllamaJsonClient(
        settings=settings
    )

    monkeypatch.setattr(
        client,
        "ensure_model_available",
        AsyncMock(return_value=None),
    )

    request_mock = AsyncMock(
        side_effect=[
            _chat_payload(
                done=False,
                content='{"markdown":"잘린 응답',
            ),
            _chat_payload(
                done=True,
                content='{"markdown":"정상 응답입니다."}',
            ),
        ]
    )

    monkeypatch.setattr(
        client,
        "_request_chat",
        request_mock,
    )

    result = await client.generate_json(
        system_prompt="system",
        user_prompt="user",
    )

    assert result == {
        "markdown": "정상 응답입니다."
    }
    assert request_mock.await_count == 2


@pytest.mark.asyncio
async def test_generate_json_retries_on_repeated_output(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = OllamaSettings(
        base_url="http://127.0.0.1:11434",
        model="test-model",
        timeout_seconds=30,
        temperature=0.3,
        max_retries=1,
        retry_delay_seconds=0,
    )

    client = OllamaJsonClient(
        settings=settings
    )

    monkeypatch.setattr(
        client,
        "ensure_model_available",
        AsyncMock(return_value=None),
    )

    request_mock = AsyncMock(
        side_effect=[
            _chat_payload(
                done=True,
                content=(
                    '{"markdown":"own own own own own own"}'
                ),
            ),
            _chat_payload(
                done=True,
                content=(
                    '{"markdown":"정상적으로 생성된 본문입니다."}'
                ),
            ),
        ]
    )

    monkeypatch.setattr(
        client,
        "_request_chat",
        request_mock,
    )

    result = await client.generate_json(
        system_prompt="system",
        user_prompt="user",
    )

    assert result["markdown"] == (
        "정상적으로 생성된 본문입니다."
    )
    assert request_mock.await_count == 2


@pytest.mark.asyncio
async def test_incomplete_json_is_not_repaired_when_done_false(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = OllamaSettings(
        base_url="http://127.0.0.1:11434",
        model="test-model",
        timeout_seconds=30,
        temperature=0.3,
        max_retries=0,
        retry_delay_seconds=0,
    )

    client = OllamaJsonClient(
        settings=settings
    )

    monkeypatch.setattr(
        client,
        "ensure_model_available",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        client,
        "_request_chat",
        AsyncMock(
            return_value=_chat_payload(
                done=False,
                content='{"markdown":"중간에 잘린 본문',
            )
        ),
    )

    with pytest.raises(
        OllamaClientError,
        match="완료되지",
    ):
        await client.generate_json(
            system_prompt="system",
            user_prompt="user",
        )
