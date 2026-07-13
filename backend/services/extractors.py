"""파일 유형별 텍스트 추출.

Phase 2 지원 범위: txt, md, csv, xlsx, pdf, url
(hwp/hwpx/docx는 Phase 2.5 이후 — 별도 파서 라이브러리 필요)
"""

import re
from pathlib import Path

SUPPORTED_FILE_TYPES = {"txt", "md", "csv", "xlsx", "pdf"}

MAX_EXTRACT_CHARS = 20000


def extract_text(file_path: str, source_type: str) -> str:
    if source_type not in SUPPORTED_FILE_TYPES:
        raise ValueError(f"unsupported source_type for file extraction: {source_type}")

    if source_type in ("txt", "md"):
        text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    elif source_type == "csv":
        text = _extract_tabular(file_path, sheet=None)
    elif source_type == "xlsx":
        text = _extract_tabular(file_path, sheet="__all__")
    elif source_type == "pdf":
        text = _extract_pdf(file_path)
    else:  # pragma: no cover
        raise ValueError(f"unhandled source_type: {source_type}")

    return text[:MAX_EXTRACT_CHARS]


def _extract_tabular(file_path: str, sheet: str | None) -> str:
    import pandas as pd

    parts: list[str] = []
    if sheet is None:
        df = pd.read_csv(file_path)
        parts.append(_dataframe_summary(df))
    else:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            parts.append(f"[Sheet: {sheet_name}]\n{_dataframe_summary(df)}")
    return "\n\n".join(parts)


def _dataframe_summary(df) -> str:
    lines = [
        f"columns: {list(df.columns)}",
        f"rows: {len(df)}",
        "preview:",
        df.head(15).to_string(),
    ]
    try:
        lines.append("stats:")
        lines.append(df.describe(include="all").to_string())
    except Exception:
        pass
    return "\n".join(lines)


def _extract_pdf(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts = []
    for i, page in enumerate(reader.pages):
        parts.append(f"[Page {i + 1}]\n{page.extract_text() or ''}")
    return "\n\n".join(parts)


def extract_url(url: str, *, http_get=None) -> tuple[str, str]:
    """URL을 가져와 (title, text)를 반환한다.

    http_get을 주입받게 해서 테스트에서 실제 네트워크 요청 없이 검증 가능하게 한다.
    """
    if http_get is None:
        import httpx

        def http_get(u: str) -> str:
            resp = httpx.get(u, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.text

    html = http_get(url)

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = title_match.group(1).strip() if title_match else url

    text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return title, text[:MAX_EXTRACT_CHARS]
