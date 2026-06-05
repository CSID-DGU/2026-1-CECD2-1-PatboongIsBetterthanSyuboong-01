"""
엑셀 원본 행 단위 train / test CSV 생성 (평가용, GraphDB 파이프라인과 분리).

- 비율: train : test ≈ 5 : 1 (행 수 기준, test 크기는 round(n/6) 후 train과 맞춤)
- 재현: random seed 고정
- 선택: 그룹 컬럼(누수 방지) → GroupShuffleSplit
- 선택: 층화 컬럼 → StratifiedShuffleSplit (불가 시 단순 셔플로 폴백)
- 출력: UTF-8-SIG CSV, split_metadata.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, StratifiedShuffleSplit

from read_excel import excel_path
from text_utils import clean_string_cell, norm_code, normalize_column_names

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TRAIN_DIR = BASE_DIR / "train_dataset"
DEFAULT_TEST_DIR = BASE_DIR / "test_dataset"
DEFAULT_TRAIN_NAME = "train.csv"
DEFAULT_TEST_NAME = "test.csv"
DEFAULT_META_NAME = "split_metadata.json"

CANONICAL_COLS = [
    "상병코드",
    "내원번호",
    "처방시퀀스",
    "처방코드",
    "처방명",
    "특이사항",
]


def _train_test_sizes(n: int) -> tuple[int, int, str]:
    """
    목표 비율 5:1에 맞추 test 행 수를 정한다.
    n==1 은 평가 분할이 의미 없어 train만 둔다.
    """
    if n <= 0:
        return 0, 0, "empty"
    if n == 1:
        return 1, 0, "n==1: test 비움(평가 분할 불가)"
    test_n = max(1, round(n / 6))
    test_n = min(test_n, n - 1)
    train_n = n - test_n
    note = f"train={train_n}, test={test_n}, target_ratio=5:1 (test≈round(n/6))"
    return train_n, test_n, note


def _excel_row_1based(index: pd.Index) -> pd.Series:
    """pandas 행 인덱스(0부터) → 엑셀 상 행 번호(헤더 1행 가정 시 데이터는 2행부터)."""
    return pd.Series(index + 2, index=index, dtype="Int64")


def _stratify_labels(s: pd.Series) -> tuple[pd.Series, str]:
    """층화용 이산 라벨. 결측은 문자열 '__NA__' 로 통일."""
    out = s.map(norm_code).astype(object)
    out = out.where(out.notna(), "__NA__")
    out = out.astype(str)
    vc = out.value_counts()
    rare = vc[vc < 2]
    if len(rare) > 0:
        return out, f"클래스당 최소 2행 미만 라벨 {len(rare)}개 → 층화 불가"
    return out, ""


def _split_indices(
    n: int,
    train_n: int,
    test_n: int,
    seed: int,
    *,
    groups: np.ndarray | None,
    y_strat: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, str]:
    """train/test 인덱스 배열 반환. 메시지는 폴백 사유."""
    rng = np.random.RandomState(seed)
    idx = np.arange(n)

    if groups is not None:
        gss = GroupShuffleSplit(n_splits=1, test_size=test_n / n, random_state=seed)
        tr, te = next(gss.split(np.zeros((n, 1)), groups=groups))
        return tr, te, "group_split(GroupShuffleSplit, test_size 비율=test_n/n)"

    if y_strat is not None:
        try:
            sss = StratifiedShuffleSplit(
                n_splits=1, test_size=test_n, random_state=seed
            )
            tr, te = next(sss.split(np.zeros((n, 1)), y_strat))
            return tr, te, "stratified(StratifiedShuffleSplit)"
        except ValueError as e:
            rng.shuffle(idx)
            te = idx[:test_n]
            tr = idx[test_n:]
            return tr, te, f"stratify 실패 → shuffle 폴백: {e}"

    rng.shuffle(idx)
    te = idx[:test_n]
    tr = idx[test_n:]
    return tr, te, "shuffle_only"


def build_split_frame(
    df: pd.DataFrame,
    *,
    seed: int,
    stratify_col: str | None,
    group_col: str | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    n = len(df)
    train_n, test_n, size_note = _train_test_sizes(n)

    meta: dict[str, Any] = {
        "seed": seed,
        "n_total": n,
        "n_train": train_n,
        "n_test": test_n,
        "size_rule": size_note,
    }

    out = df.copy().reset_index(drop=True)
    out["source_row_index"] = np.arange(n, dtype=int)
    out["excel_row_1based"] = _excel_row_1based(out.index).values

    if test_n == 0:
        out["split"] = "train"
        meta["split_mode"] = "all_train"
        meta["stratify_col"] = stratify_col
        meta["group_col"] = group_col
        return out, meta

    groups_arr: np.ndarray | None = None
    y_strat_arr: np.ndarray | None = None
    stratify_msg = ""

    if group_col is not None:
        if group_col not in out.columns:
            raise ValueError(f"group_col 없음: {group_col!r}")
        g = out[group_col].map(clean_string_cell).astype(str)
        g = g.replace("<NA>", "__NA__")
        groups_arr = pd.factorize(g, sort=True)[0]
        meta["group_col"] = group_col
        meta["n_groups"] = int(pd.Series(groups_arr).nunique())

    if group_col is None and stratify_col is not None:
        if stratify_col not in out.columns:
            raise ValueError(f"stratify_col 없음: {stratify_col!r}")
        y_labels, stratify_msg = _stratify_labels(out[stratify_col])
        meta["stratify_col"] = stratify_col
        if stratify_msg:
            meta["stratify_note"] = stratify_msg
        else:
            y_strat_arr = y_labels.values

    tr_idx, te_idx, split_mode = _split_indices(
        n, train_n, test_n, seed, groups=groups_arr, y_strat=y_strat_arr
    )
    meta["split_mode"] = split_mode

    split_col = np.array(["train"] * n, dtype=object)
    split_col[te_idx] = "test"
    out["split"] = split_col

    if stratify_col and stratify_col in out.columns:
        def _vc_dict(s: pd.Series) -> dict[str, int]:
            vc = s.map(norm_code).astype(str).value_counts().head(50)
            return {str(k): int(v) for k, v in vc.items()}

        meta["stratify_distribution"] = {
            "train": _vc_dict(out.loc[out["split"] == "train", stratify_col]),
            "test": _vc_dict(out.loc[out["split"] == "test", stratify_col]),
        }

    return out, meta


def run_cli() -> int:
    p = argparse.ArgumentParser(
        description="엑셀 행 단위 train/test CSV (5:1, UTF-8-SIG) 생성"
    )
    p.add_argument(
        "--excel",
        type=Path,
        default=None,
        help="xlsx 경로 (미지정 시 read_excel.excel_path() 패턴 파일)",
    )
    p.add_argument(
        "--sheet",
        default=0,
        help="시트명 또는 인덱스 (pandas read_excel과 동일)",
    )
    p.add_argument(
        "--train-dir",
        type=Path,
        default=DEFAULT_TRAIN_DIR,
        help="train.csv 저장 디렉터리 (기본: data_normalize/train_dataset)",
    )
    p.add_argument(
        "--test-dir",
        type=Path,
        default=DEFAULT_TEST_DIR,
        help="test.csv / split_metadata.json 저장 디렉터리 (기본: data_normalize/test_dataset)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--stratify-col",
        default=None,
        help="층화 기준 컬럼 (예: 상병코드). group-col 지정 시 무시됨",
    )
    p.add_argument(
        "--group-col",
        default=None,
        help="누수 방지 그룹 키 (예: 내원번호). 지정 시 그룹 단위로 train/test",
    )
    args = p.parse_args()

    sheet_arg: str | int = args.sheet
    if isinstance(sheet_arg, str) and sheet_arg.isdigit():
        sheet_arg = int(sheet_arg)

    path = args.excel.expanduser().resolve() if args.excel else excel_path()
    if not path.is_file():
        print(f"파일 없음: {path}", file=sys.stderr)
        return 1

    raw = pd.read_excel(path, sheet_name=sheet_arg, engine="openpyxl")
    df = normalize_column_names(raw, CANONICAL_COLS)

    out, meta = build_split_frame(
        df,
        seed=args.seed,
        stratify_col=args.stratify_col,
        group_col=args.group_col,
    )
    meta["excel_path"] = str(path)
    meta["sheet"] = sheet_arg

    train_dir = args.train_dir
    test_dir = args.test_dir
    train_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    train_df = out[out["split"] == "train"].drop(columns=["split"])
    test_df = out[out["split"] == "test"].drop(columns=["split"])

    train_path = train_dir / DEFAULT_TRAIN_NAME
    test_path = test_dir / DEFAULT_TEST_NAME
    meta_path = test_dir / DEFAULT_META_NAME

    train_df.to_csv(train_path, index=False, encoding="utf-8-sig")
    test_df.to_csv(test_path, index=False, encoding="utf-8-sig")

    meta["output"] = {
        "train_csv": str(train_path),
        "test_csv": str(test_path),
        "metadata_json": str(meta_path),
    }
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"저장: {train_path} ({len(train_df)}행)")
    print(f"저장: {test_path} ({len(test_df)}행)")
    print(f"메타: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
