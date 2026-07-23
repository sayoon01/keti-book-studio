from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.llm import (
    OllamaClient,
    OllamaClientError,
    OllamaIncompleteResponseError,
    OllamaSettings,
)


def _generate_payload(
    *,
    content: str,
) -> dict:
    return {
        "done": True,
        "done_reason": "stop",
        "response": content,
        "total_duration": 1_000_000_000,
    }


def _test_settings(
    *,
    max_retries: int,
) -> OllamaSettings:
    return OllamaSettings(
        base_url="http://127.0.0.1:11434",
        timeout_seconds=30,
        max_retries=max_retries,
        retry_delay_seconds=0,
        keep_alive="2m",
    )


@pytest.mark.asyncio
async def test_generate_json_retries_when_incomplete(
    monkeypatch: pytest.MonkeyPatch,
):
    client = OllamaClient(
        settings=_test_settings(max_retries=1)
    )

    monkeypatch.setattr(
        client,
        "_ensure_model_available",
        AsyncMock(return_value=None),
    )

    request_mock = AsyncMock(
        side_effect=[
            OllamaIncompleteResponseError(
                "Ollama 생성이 완료되지 않았습니다."
            ),
            _generate_payload(
                content='{"markdown":"정상 응답입니다."}',
            ),
        ]
    )

    monkeypatch.setattr(
        client,
        "_request",
        request_mock,
    )

    result = await client.generate_json(
        model="test-model",
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        num_predict=256,
        num_ctx=2048,
    )

    assert result.data == {
        "markdown": "정상 응답입니다."
    }
    assert request_mock.await_count == 2
    assert result.metadata.attempts == 2


@pytest.mark.asyncio
async def test_generate_text_rejects_short_output(
    monkeypatch: pytest.MonkeyPatch,
):
    client = OllamaClient(
        settings=_test_settings(max_retries=0)
    )

    monkeypatch.setattr(
        client,
        "_ensure_model_available",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        client,
        "_request",
        AsyncMock(
            return_value=_generate_payload(
                content="짧음",
            )
        ),
    )

    with pytest.raises(
        OllamaClientError,
        match="너무 짧습니다",
    ):
        await client.generate_text(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            temperature=0.4,
            num_predict=256,
            num_ctx=2048,
            minimum_length=300,
        )


@pytest.mark.asyncio
async def test_incomplete_response_fails_after_retries(
    monkeypatch: pytest.MonkeyPatch,
):
    client = OllamaClient(
        settings=_test_settings(max_retries=0)
    )

    monkeypatch.setattr(
        client,
        "_ensure_model_available",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        client,
        "_request",
        AsyncMock(
            side_effect=OllamaIncompleteResponseError(
                "Ollama 생성이 완료되지 않았습니다."
            )
        ),
    )

    with pytest.raises(
        OllamaClientError,
        match="생성에 실패",
    ):
        await client.generate_json(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            temperature=0.2,
            num_predict=256,
            num_ctx=2048,
        )
