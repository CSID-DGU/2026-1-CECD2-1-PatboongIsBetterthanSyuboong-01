"""
원본 엑셀(20260406_상병별 처방코드 추출_특이사항 추가.xlsx)을 pandas로 읽기 위한 모듈.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_BASE = Path(__file__).resolve().parent
_INPUT_DIR = _BASE / "input"
# 동일 의미의 파일명이 OS에 따라 NFC/NFD 등으로 다를 수 있어 접두사로 탐색
_EXCEL_GLOB = "20260406_*.xlsx"


def excel_path() -> Path:
    """input/ 또는 data_normalize 루트의 원본 xlsx 단일 파일 경로."""
    for root in (_INPUT_DIR, _BASE):
        matches = sorted(root.glob(_EXCEL_GLOB))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise FileNotFoundError(
                f"{root} 에 xlsx가 여러 개입니다. 하나만 두세요: {matches}"
            )
    raise FileNotFoundError(
        f"{_INPUT_DIR} 또는 {_BASE} 에 {_EXCEL_GLOB} 패턴의 xlsx가 없습니다."
    )


def read_excel(
    sheet_name: str | int | list | None = 0,
    **kwargs,
) -> pd.DataFrame | dict[str | int, pd.DataFrame]:
    """
    원본 통합 엑셀을 읽는다.

    Parameters
    ----------
    sheet_name
        pandas.read_excel 과 동일. 기본값 0 (첫 시트).
    **kwargs
        pandas.read_excel 에 그대로 전달 (header, dtype 등).
    """
    path = excel_path()
    return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl", **kwargs)


def sheet_names() -> list[str]:
    """통합 파일에 포함된 시트 이름 목록."""
    path = excel_path()
    xl = pd.ExcelFile(path, engine="openpyxl")
    return xl.sheet_names


if __name__ == "__main__":
    p = excel_path()
    print(f"파일: {p}")
    print(f"시트: {sheet_names()}")
    df0 = read_excel(sheet_name=0)
    print(f"첫 시트 shape: {df0.shape}")
    print(df0.head())
