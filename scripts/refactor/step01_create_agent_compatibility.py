from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE = PROJECT_ROOT / "backend" / "agents"


MODULE_MAP = {
    "base.py": (
        "backend.orchestration.stages.base"
    ),
    "registry.py": (
        "backend.orchestration.stages.registry"
    ),
    "context.py": (
        "backend.orchestration.context"
    ),
    "context_builder.py": (
        "backend.orchestration.context_builder"
    ),
    "schemas.py": (
        "backend.orchestration.agent_schemas"
    ),
    "planner.py": (
        "backend.orchestration.stages.planner_stage"
    ),
    "researcher.py": (
        "backend.orchestration.stages.researcher_stage"
    ),
    "writer.py": (
        "backend.orchestration.stages.writer_stage"
    ),
    "reviewer.py": (
        "backend.orchestration.stages.reviewer_stage"
    ),
    "editor.py": (
        "backend.orchestration.stages.editor_stage"
    ),
    "reviser.py": (
        "backend.orchestration.stages.reviser_stage"
    ),
    "reader.py": (
        "backend.orchestration.stages.reader_stage"
    ),
    "finalizer.py": (
        "backend.orchestration.stages.finalizer_stage"
    ),
}


TEMPLATE = '''"""
Deprecated compatibility module.

새 코드는 `{new_module}`을 사용해야 합니다.
이 파일은 기존 import가 즉시 깨지지 않도록 임시로 유지합니다.
"""

from {new_module} import *  # noqa: F401,F403
'''


def main() -> None:
    OLD_PACKAGE.mkdir(
        parents=True,
        exist_ok=True,
    )

    init_file = OLD_PACKAGE / "__init__.py"

    init_file.write_text(
        '''"""
Deprecated compatibility package.

새 코드는 backend.orchestration.stages를 사용하세요.
"""
''',
        encoding="utf-8",
    )

    print(
        "[WRITE]",
        init_file.relative_to(PROJECT_ROOT),
    )

    for filename, new_module in MODULE_MAP.items():
        path = OLD_PACKAGE / filename

        path.write_text(
            TEMPLATE.format(
                new_module=new_module,
            ),
            encoding="utf-8",
        )

        print(
            "[WRITE]",
            path.relative_to(PROJECT_ROOT),
        )


if __name__ == "__main__":
    main()
