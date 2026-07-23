from __future__ import annotations

import pytest

from backend.generation.model_router import (
    GenerationRole,
    ModelRouter,
)


def test_model_router_uses_common_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_MODEL",
        "common-model",
    )

    monkeypatch.delenv(
        "BOOK_STUDIO_WRITER_MODEL",
        raising=False,
    )

    router = ModelRouter()

    config = router.get_config(
        GenerationRole.WRITER
    )

    assert config.model == "common-model"
    assert config.role == GenerationRole.WRITER


def test_model_router_uses_role_specific_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_MODEL",
        "common-model",
    )

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
        "BOOK_STUDIO_TEMPERATURE",
        "0.3",
    )

    monkeypatch.setenv(
        "BOOK_STUDIO_WRITER_TEMPERATURE",
        "0.7",
    )

    router = ModelRouter()

    config = router.get_config(
        GenerationRole.WRITER
    )

    assert config.temperature == 0.7


def test_model_router_rejects_unknown_role():
    router = ModelRouter()

    with pytest.raises(
        ValueError,
        match="지원하지 않는 Generation 역할",
    ):
        router.get_config(
            "unknown-role"
        )


def test_model_router_rejects_invalid_temperature(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "BOOK_STUDIO_REVIEWER_TEMPERATURE",
        "not-number",
    )

    router = ModelRouter()

    with pytest.raises(
        ValueError,
        match="숫자여야 합니다",
    ):
        router.get_config(
            GenerationRole.REVIEWER
        )
