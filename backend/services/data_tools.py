"""표/차트용 데이터 계산.

Data Agent가 사용하는 순수 함수 모음. LLM은 '무엇을 어떻게 보여줄지'만 결정하고
(Visual Planner), 실제 숫자 계산은 여기 pandas 함수가 담당한다 —
LLM이 통계치를 추측/환각하지 않도록 하기 위함.
"""

import pandas as pd


def _load_dataframe(file_path: str, source_type: str, sheet: str | None = None) -> pd.DataFrame:
    if source_type == "csv":
        return pd.read_csv(file_path)
    if source_type == "xlsx":
        xls = pd.ExcelFile(file_path)
        sheet_name = sheet or xls.sheet_names[0]
        return xls.parse(sheet_name)
    raise ValueError(f"표/차트 생성은 csv/xlsx만 지원합니다: {source_type}")


def get_columns(file_path: str, source_type: str, sheet: str | None = None) -> list[str]:
    df = _load_dataframe(file_path, source_type, sheet)
    return list(df.columns)


def load_table(file_path: str, source_type: str, sheet: str | None = None, max_rows: int = 50) -> dict:
    df = _load_dataframe(file_path, source_type, sheet)
    preview = df.head(max_rows)
    safe = preview.astype(object).where(preview.notna(), None)
    return {
        "columns": list(preview.columns),
        "rows": safe.values.tolist(),
        "total_rows": len(df),
    }


def compute_chart_data(
    file_path: str,
    source_type: str,
    *,
    category_column: str | None = None,
    value_column: str | None = None,
    sheet: str | None = None,
    agg: str = "mean",
) -> dict:
    df = _load_dataframe(file_path, source_type, sheet)

    numeric_cols = list(df.select_dtypes(include="number").columns)
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    if value_column is None:
        if not numeric_cols:
            raise ValueError("숫자형 컬럼이 없어 차트를 만들 수 없습니다.")
        value_column = numeric_cols[0]
    elif value_column not in df.columns:
        raise ValueError(f"존재하지 않는 컬럼입니다: {value_column}")

    if category_column is None:
        category_column = non_numeric_cols[0] if non_numeric_cols else None
    elif category_column not in df.columns:
        raise ValueError(f"존재하지 않는 컬럼입니다: {category_column}")

    if category_column:
        grouped = df.groupby(category_column)[value_column].agg(agg).sort_values(ascending=False)
        labels = [str(x) for x in grouped.index.tolist()]
        values = [float(x) for x in grouped.values.tolist()]
    else:
        labels = [str(i) for i in df.index.tolist()]
        values = [float(x) for x in df[value_column].tolist()]

    return {
        "category_column": category_column,
        "value_column": value_column,
        "agg": agg,
        "labels": labels,
        "values": values,
    }
