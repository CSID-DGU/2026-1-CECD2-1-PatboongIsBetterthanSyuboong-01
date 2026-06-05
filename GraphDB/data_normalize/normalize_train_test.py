"""
split_train_test_csv.py 가 만든 train.csv / test.csv 각각에 대해
graph_normalize 와 동일한 정규화·검증 파이프라인을 적용한다.

- graph_normalize.py 는 손대지 않고, 그 안의 step/build/validate 함수만 import 해서
  CSV 입력 + split 별 출력 디렉터리 분리 형태로 다시 오케스트레이션한다.
- 입력 기본값:
    train: data_normalize/train_dataset/train.csv
    test : data_normalize/test_dataset/test.csv
- 출력 기본값:
    train: data_normalize/train_dataset/output/*.csv,  logs/*.csv
    test : data_normalize/test_dataset/output/*.csv,   logs/*.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from graph_normalize import (
    CANONICAL_COLS,
    build_diagnosis_mention_edges,
    build_node_tables,
    build_prescription_mention_edges,
    build_relationship_tables,
    save_csv,
    step_add_ids,
    step_add_norm_columns,
    step_clean_base_columns,
    step_mark_and_drop_full_duplicates,
    validate_graph,
)
from note_mentions import build_mention_tables
from text_utils import normalize_column_names

BASE_DIR = Path(__file__).resolve().parent
TRAIN_DIR = BASE_DIR / "train_dataset"
TEST_DIR = BASE_DIR / "test_dataset"

META_COLS_TO_DROP = ("source_row_index", "excel_row_1based", "split")

OUTPUT_FILE_MAP_NODES = {
    "01_visit_nodes.csv": "visit_nodes",
    "02_diagnosis_nodes.csv": "diagnosis_nodes",
    "03_prescription_master_nodes.csv": "prescription_master_nodes",
    "04_order_line_nodes.csv": "order_line_nodes",
    "05_special_note_nodes.csv": "special_note_nodes",
    "06_note_mention_nodes.csv": "note_mention_nodes",
}
OUTPUT_FILE_MAP_RELS = {
    "11_rel_visit_has_diagnosis.csv": "visit_has_diagnosis",
    "12_rel_visit_has_order.csv": "visit_has_order",
    "13_rel_order_refers_to_prescription.csv": "order_refers_to_prescription",
    "14_rel_visit_has_note.csv": "visit_has_note",
    "15_rel_order_associated_with_diagnosis.csv": "order_associated_with_diagnosis",
    "16_rel_note_has_mention.csv": "note_has_mention",
    "17_rel_diagnosis_has_mention.csv": "diagnosis_has_mention",
    "18_rel_prescription_has_mention.csv": "prescription_has_mention",
}


def _load_split_csv(path: Path) -> pd.DataFrame:
    """split CSV 로딩: 빈 문자열은 NA, dtype 은 object 로 통일."""
    if not path.is_file():
        raise FileNotFoundError(f"입력 CSV 없음: {path}")
    df = pd.read_csv(path, dtype=object, keep_default_na=False, na_values=[""])
    drop_cols = [c for c in META_COLS_TO_DROP if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    return normalize_column_names(df, CANONICAL_COLS)


def _normalize_split(
    name: str,
    csv_path: Path,
    base_dir: Path,
) -> tuple[list[str], pd.DataFrame]:
    """단일 split(train 또는 test) CSV 에 정규화 파이프라인 적용."""
    output_dir = base_dir / "output"
    logs_dir = base_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    profile_rows: list[dict[str, Any]] = []

    raw = _load_split_csv(csv_path)
    profile_rows.append({"step": f"load_{name}_csv", "rows": len(raw), "note": ""})
    profile_rows.append({"step": "column_names_fixed", "rows": len(raw), "note": ""})

    df = step_clean_base_columns(raw)
    df = step_add_norm_columns(df)
    df = step_add_ids(df)
    profile_rows.append({"step": "after_id_columns", "rows": len(df), "note": ""})

    df_dedup, df_dup_flagged, dup_meta = step_mark_and_drop_full_duplicates(df)
    save_csv(df_dup_flagged, logs_dir / "step06_full_row_duplicate_flags.csv")
    profile_rows.append(
        {
            "step": dup_meta["step"],
            "rows": dup_meta["rows_after"],
            "note": (
                f"before={dup_meta['rows_before']} removed={dup_meta['removed_rows']} "
                f"is_duplicate_row_true={dup_meta['duplicate_row_count']}"
            ),
        }
    )

    nodes = build_node_tables(df_dedup)
    rels = build_relationship_tables(df_dedup)

    mention_nodes, rel_note_mention = build_mention_tables(nodes["special_note_nodes"])
    nodes["note_mention_nodes"] = mention_nodes
    rels["note_has_mention"] = rel_note_mention
    rels["diagnosis_has_mention"] = build_diagnosis_mention_edges(df_dedup, mention_nodes)
    rels["prescription_has_mention"] = build_prescription_mention_edges(
        df_dedup, mention_nodes
    )

    errs = validate_graph(nodes, rels)

    for fname, key in OUTPUT_FILE_MAP_NODES.items():
        save_csv(nodes[key], output_dir / fname)
    for fname, key in OUTPUT_FILE_MAP_RELS.items():
        save_csv(rels[key], output_dir / fname)

    summary = pd.DataFrame(profile_rows)
    summary["rows"] = summary["rows"].astype("Int64")
    extra = pd.DataFrame(
        [
            {"step": "nodes_visit", "rows": len(nodes["visit_nodes"]), "note": ""},
            {"step": "nodes_diagnosis", "rows": len(nodes["diagnosis_nodes"]), "note": ""},
            {
                "step": "nodes_prescription_master",
                "rows": len(nodes["prescription_master_nodes"]),
                "note": "",
            },
            {
                "step": "nodes_order_line",
                "rows": len(nodes["order_line_nodes"]),
                "note": f"fact_rows_after_dedup={len(df_dedup)}",
            },
            {"step": "nodes_special_note", "rows": len(nodes["special_note_nodes"]), "note": ""},
            {"step": "nodes_note_mention", "rows": len(nodes["note_mention_nodes"]), "note": ""},
            {"step": "rels_note_has_mention", "rows": len(rels["note_has_mention"]), "note": ""},
            {
                "step": "rels_diagnosis_has_mention",
                "rows": len(rels["diagnosis_has_mention"]),
                "note": "",
            },
            {
                "step": "rels_prescription_has_mention",
                "rows": len(rels["prescription_has_mention"]),
                "note": "",
            },
            {
                "step": "validation_ok",
                "rows": len(errs),
                "note": "; ".join(errs) if errs else "ok",
            },
        ]
    )
    profiling = pd.concat([summary, extra], ignore_index=True)
    save_csv(profiling, logs_dir / "profiling_summary.csv")

    return errs, profiling


def run_cli() -> int:
    p = argparse.ArgumentParser(
        description="train.csv / test.csv 각각에 graph_normalize 와 동일한 파이프라인 적용"
    )
    p.add_argument("--train-csv", type=Path, default=TRAIN_DIR / "train.csv")
    p.add_argument("--test-csv", type=Path, default=TEST_DIR / "test.csv")
    p.add_argument(
        "--train-base",
        type=Path,
        default=TRAIN_DIR,
        help="train 산출물(output/, logs/) 베이스 디렉터리",
    )
    p.add_argument(
        "--test-base",
        type=Path,
        default=TEST_DIR,
        help="test 산출물(output/, logs/) 베이스 디렉터리",
    )
    p.add_argument("--only", choices=["train", "test", "both"], default="both")
    args = p.parse_args()

    targets: list[tuple[str, Path, Path]] = []
    if args.only in ("train", "both"):
        targets.append(("train", args.train_csv, args.train_base))
    if args.only in ("test", "both"):
        targets.append(("test", args.test_csv, args.test_base))

    all_errors: dict[str, list[str]] = {}
    for name, csv_path, base in targets:
        print(f"[{name}] 입력: {csv_path}")
        errs, prof = _normalize_split(name, csv_path, base)
        print(f"[{name}] 출력: {base / 'output'}")
        print(f"[{name}] 로그: {base / 'logs'}")
        print(f"--- [{name}] profiling ---")
        print(prof.to_string(index=False))
        if errs:
            all_errors[name] = errs

    if all_errors:
        print("--- 검증 경고/오류 ---", file=sys.stderr)
        for name, errs in all_errors.items():
            for e in errs:
                print(f"[{name}] {e}", file=sys.stderr)
        return 1

    print("완료: 각 split 의 output/*.csv, logs/profiling_summary.csv 생성")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
