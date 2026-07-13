"""Persona MD 파일을 디스크에 저장/조회하는 유틸.

DB의 Persona.files 는 {"PERSONA.md": "data/personas/technical_expert/PERSONA.md", ...}
형태로 파일 경로만 들고 있고, 실제 내용은 디스크의 마크다운 파일에 있다.
"""

import os
from pathlib import Path

PERSONA_DIR = Path(os.environ.get("KETI_PERSONA_DIR", "data/personas"))

STANDARD_FILES = ["PERSONA.md", "planner.md", "writer.md", "reviewer.md", "visual_policy.md"]


def persona_slug_dir(slug: str) -> Path:
    return PERSONA_DIR / slug


def write_persona_files(slug: str, file_contents: dict[str, str]) -> dict[str, str]:
    target_dir = persona_slug_dir(slug)
    target_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    for filename, content in file_contents.items():
        path = target_dir / filename
        path.write_text(content, encoding="utf-8")
        paths[filename] = str(path)
    return paths


def read_persona_files(files: dict[str, str]) -> dict[str, str]:
    contents = {}
    for filename, path in files.items():
        p = Path(path)
        contents[filename] = p.read_text(encoding="utf-8") if p.exists() else ""
    return contents


def clone_persona_files(source_slug: str, target_slug: str) -> dict[str, str]:
    source_dir = persona_slug_dir(source_slug)
    contents = {}
    for filename in STANDARD_FILES:
        src_path = source_dir / filename
        if src_path.exists():
            contents[filename] = src_path.read_text(encoding="utf-8")
    return write_persona_files(target_slug, contents)
