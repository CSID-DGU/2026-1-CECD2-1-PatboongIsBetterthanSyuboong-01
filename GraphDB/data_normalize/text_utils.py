"""문자열 정리·정규화 유틸."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _collapse_ws(s: str) -> str:
    s = s.replace("\r", "").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def clean_string_cell(value: Any) -> Any:
    """strip, 줄바꿈 제거, 다중공백 축소, 빈 문자열은 NA."""
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        t = str(value)
    elif isinstance(value, int):
        t = str(int(value))
    elif isinstance(value, float):
        if pd.isna(value):
            return pd.NA
        if value.is_integer():
            t = str(int(value))
        else:
            t = str(value).strip()
    else:
        t = str(value)
    t = _collapse_ws(t)
    if t == "":
        return pd.NA
    return t


def clean_string_series(s: pd.Series) -> pd.Series:
    return s.map(clean_string_cell)


def norm_code(value: Any) -> Any:
    """처방·상병 코드용: clean 후 대문자."""
    v = clean_string_cell(value)
    if pd.isna(v):
        return pd.NA
    return str(v).upper()


def norm_text(value: Any) -> Any:
    """처방명·특이사항 등: clean만 (대소문자 유지)."""
    return clean_string_cell(value)


def normalize_column_names(df: pd.DataFrame, canonical: list[str]) -> pd.DataFrame:
    """헤더의 공백·숨은 개행 제거 후 표준 컬럼명으로 맞춘다."""
    raw = [str(c).replace("\r", "").replace("\n", "").strip() for c in df.columns]
    cleaned = [re.sub(r"\s+", "", x) for x in raw]
    # 한글 컬럼: 공백 제거한 키로 기대치와 매칭
    expected = {re.sub(r"\s+", "", k): k for k in canonical}
    new_cols = []
    for c in cleaned:
        if c not in expected:
            raise ValueError(f"알 수 없는 컬럼명: {c!r} (기대: {canonical})")
        new_cols.append(expected[c])
    out = df.copy()
    out.columns = new_cols
    return out[canonical]
