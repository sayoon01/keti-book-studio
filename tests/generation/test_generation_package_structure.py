from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_generation_service_is_importable():
    module = importlib.import_module(
        "backend.generation.chapter_generation_service"
    )

    assert hasattr(
        module,
        "ChapterGenerationService",
    )


def test_model_router_is_importable():
    module = importlib.import_module(
        "backend.generation.model_router"
    )

    assert hasattr(
        module,
        "ModelRouter",
    )


def test_artifact_payload_validator_moved():
    path = (
        PROJECT_ROOT
        / "backend"
        / "generation"
        / "validators"
        / "artifact_payloads.py"
    )

    assert path.exists()


def test_ollama_client_moved_to_infrastructure():
    path = (
        PROJECT_ROOT
        / "backend"
        / "infrastructure"
        / "llm"
        / "ollama_json_client.py"
    )

    assert path.exists()


def test_old_generation_modules_are_compatibility_modules():
    old_paths = [
        (
            PROJECT_ROOT
            / "backend"
            / "orchestration"
            / "chapter_llm_service.py"
        ),
        (
            PROJECT_ROOT
            / "backend"
            / "orchestration"
            / "artifact_payloads.py"
        ),
        (
            PROJECT_ROOT
            / "backend"
            / "llm"
            / "ollama_json_client.py"
        ),
    ]

    for path in old_paths:
        content = path.read_text(
            encoding="utf-8",
        )

        assert "Deprecated compatibility" in content
