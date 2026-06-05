#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
환자(내원번호) 단위 3분할 스크립트.

- 입력 CSV(여러 개 가능)를 합친 뒤 내원번호 기준으로
  train / calibration / test 를 분리합니다.
- 같은 내원번호가 서로 다른 split에 섞이지 않도록 보장합니다.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="내원번호 단위 train/calibration/test 3분할")
    p.add_argument(
        "--input-csv",
        action="append",
        type=Path,
        default=[],
        help="입력 CSV 경로 (여러 번 지정 가능). 미지정 시 기존 train/test를 자동 사용",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=root / "three_way_split",
        help="출력 디렉터리",
    )
    p.add_argument("--train-ratio", type=float, default=0.7)
    p.add_argument("--calibration-ratio", type=float, default=0.15)
    p.add_argument("--test-ratio", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _default_inputs(root: Path) -> list[Path]:
    return [
        root / "train_dataset" / "train.csv",
        root / "test_dataset" / "test.csv",
    ]


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent

    inputs = args.input_csv or _default_inputs(base)
    for p in inputs:
        if not p.is_file():
            raise SystemExit(f"[오류] 입력 CSV 없음: {p}")

    ratio_sum = args.train_ratio + args.calibration_ratio + args.test_ratio
    if abs(ratio_sum - 1.0) > 1e-8:
        raise SystemExit(f"[오류] 비율 합은 1이어야 합니다. 현재: {ratio_sum}")

    all_rows: list[dict[str, str]] = []
    for p in inputs:
        all_rows.extend(_read_rows(p))
    if not all_rows:
        raise SystemExit("[오류] 입력 데이터가 비어 있습니다.")

    fieldnames = list(all_rows[0].keys())
    visit_key = "내원번호"
    visits = sorted({(r.get(visit_key) or "").strip() for r in all_rows if (r.get(visit_key) or "").strip()})
    if not visits:
        raise SystemExit("[오류] 내원번호 컬럼에서 유효한 키를 찾지 못했습니다.")

    rng = random.Random(args.seed)
    rng.shuffle(visits)

    n = len(visits)
    n_train = int(round(n * args.train_ratio))
    n_calib = int(round(n * args.calibration_ratio))
    n_train = max(1, min(n - 2, n_train))
    n_calib = max(1, min(n - n_train - 1, n_calib))
    n_test = n - n_train - n_calib
    if n_test <= 0:
        raise SystemExit("[오류] 분할 결과 test 방문 수가 0입니다. 비율을 조정하세요.")

    train_visits = set(visits[:n_train])
    calib_visits = set(visits[n_train : n_train + n_calib])
    test_visits = set(visits[n_train + n_calib :])

    train_rows = [r for r in all_rows if (r.get(visit_key) or "").strip() in train_visits]
    calib_rows = [r for r in all_rows if (r.get(visit_key) or "").strip() in calib_visits]
    test_rows = [r for r in all_rows if (r.get(visit_key) or "").strip() in test_visits]

    out_dir = args.out_dir
    train_path = out_dir / "train.csv"
    calib_path = out_dir / "calibration.csv"
    test_path = out_dir / "test.csv"
    _write_rows(train_path, train_rows, fieldnames)
    _write_rows(calib_path, calib_rows, fieldnames)
    _write_rows(test_path, test_rows, fieldnames)

    print(f"[완료] train={train_path}")
    print(f"[완료] calibration={calib_path}")
    print(f"[완료] test={test_path}")
    print(
        "[요약] "
        f"visits: train={len(train_visits)}, calibration={len(calib_visits)}, test={len(test_visits)} | "
        f"rows: train={len(train_rows)}, calibration={len(calib_rows)}, test={len(test_rows)}"
    )


if __name__ == "__main__":
    main()
