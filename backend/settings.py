from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
SOURCE_LIBRARY_DIR = DATA_DIR / "source_library"
EXPORTS_DIR = DATA_DIR / "exports"
PERSONAS_DIR = DATA_DIR / "personas"

MAX_DIRECTORY_FILES = 500
MAX_DIRECTORY_TOTAL_BYTES = 500 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 50 * 1024 * 1024

ALLOWED_SOURCE_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
    ".docx",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".sql",
}

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}
