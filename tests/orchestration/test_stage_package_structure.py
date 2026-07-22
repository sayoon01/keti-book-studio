from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_STAGE_MODULES = [
    "backend.orchestration.stages.base",
    "backend.orchestration.stages.registry",
    "backend.orchestration.stages.planner_stage",
    "backend.orchestration.stages.researcher_stage",
    "backend.orchestration.stages.writer_stage",
    "backend.orchestration.stages.reviewer_stage",
    "backend.orchestration.stages.editor_stage",
    "backend.orchestration.stages.reviser_stage",
    "backend.orchestration.stages.reader_stage",
    "backend.orchestration.stages.finalizer_stage",
]


def test_production_stage_modules_are_importable():
    for module_name in EXPECTED_STAGE_MODULES:
        module = importlib.import_module(
            module_name
        )

        assert module is not None


def test_old_agent_modules_are_compatibility_only():
    old_agents_dir = (
        PROJECT_ROOT
        / "backend"
        / "agents"
    )

    assert old_agents_dir.exists()

    for path in old_agents_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue

        content = path.read_text(
            encoding="utf-8",
        )

        assert "Deprecated compatibility module" in content
        assert "backend.orchestration" in content


def test_stage_files_exist_in_orchestration_package():
    stages_dir = (
        PROJECT_ROOT
        / "backend"
        / "orchestration"
        / "stages"
    )

    expected_files = {
        "base.py",
        "registry.py",
        "planner_stage.py",
        "researcher_stage.py",
        "writer_stage.py",
        "reviewer_stage.py",
        "editor_stage.py",
        "reviser_stage.py",
        "reader_stage.py",
        "finalizer_stage.py",
    }

    actual_files = {
        path.name
        for path in stages_dir.glob("*.py")
    }

    assert expected_files <= actual_files
