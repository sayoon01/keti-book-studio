from __future__ import annotations

import pytest

from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)


def test_model_router_uses_role_specific_defaults(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(
        "BOOK_STUDIO_WRITER_MODEL",
        raising=False,
    )
    monkeypatch.delenv(
        "BOOK_STUDIO_RESEARCHER_MODEL",
        raising=False,
    )

    router = ModelRouter()

    writer = router.get_config(
        GenerationRole.WRITER
    )
    researcher = router.get_config(
        GenerationRole.RESEARCHER
    )

    assert writer.model == "gemma4:31b"
    assert writer.response_format == "markdown"
    assert researcher.model == "qwen3:32b"
    assert researcher.response_format == "json"


def test_model_router_uses_role_specific_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_REVIEWER_MODEL",
        "reviewer-model",
    )

    router = ModelRouter()

    config = router.get_config(
        GenerationRole.REVIEWER
    )

    assert config.model == "reviewer-model"


def test_model_router_uses_role_temperature(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_WRITER_TEMPERATURE",
        "0.7",
    )

    router = ModelRouter()

    config = router.get_config(
        GenerationRole.WRITER
    )

    assert config.temperature == 0.7


def test_model_router_rejects_unknown_role_type():
    router = ModelRouter()

    with pytest.raises(
        TypeError,
        match="GenerationRole",
    ):
        router.get_config(
            "unknown-role"  # type: ignore[arg-type]
        )


def test_model_router_rejects_invalid_temperature(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_REVIEWER_TEMPERATURE",
        "not-number",
    )

    with pytest.raises(
        ValueError,
        match="숫자여야 합니다",
    ):
        ModelRouter()


def test_requires_technical_review_for_code_block():
    router = ModelRouter()

    assert router.requires_technical_review(
        book_type="programming"
    ) is True

    assert router.requires_technical_review(
        book_type="novel"
    ) is False

    assert router.requires_technical_review(
        book_type="education",
        chapter_text="```python\nprint(1)\n```",
    ) is True
