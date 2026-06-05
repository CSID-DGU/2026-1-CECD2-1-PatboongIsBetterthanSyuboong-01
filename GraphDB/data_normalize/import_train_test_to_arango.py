#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train.csv / test.csv 기반 그래프 CSV만 ArangoDB에 적재한다.

- 입력: ``train_dataset/output/*.csv``, ``test_dataset/output/*.csv``
  (``normalize_train_test.py`` 로 먼저 생성)
- train·test는 서로 다른 DB에 넣는 것을 권장(데이터 누수·평가 분리).

실행 (data_normalize 디렉터리에서):

  pip install -r requirements.txt
  python normalize_train_test.py
  python import_train_test_to_arango.py --dry-run
  python import_train_test_to_arango.py

환경 변수로 DB 이름을 바꿀 수 있음:
  ARANGO_TRAIN_DATABASE, ARANGO_TEST_DATABASE

LLM/백엔드는 평가 시 ``ARANGO_DATABASE``(또는 Spring ``arangodb.database``)를
학습용과 테스트용 중 하나로 맞춘다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from import_to_arango import run_import

DEFAULT_TRAIN_OUT = SCRIPT_DIR / "train_dataset" / "output"
DEFAULT_TEST_OUT = SCRIPT_DIR / "test_dataset" / "output"
DEFAULT_TRAIN_DB = "bitcomputer_graph_train"
DEFAULT_TEST_DB = "bitcomputer_graph_test"


def _maybe_normalize_first() -> None:
    norm = SCRIPT_DIR / "normalize_train_test.py"
    if not norm.is_file():
        print(f"[경고] {norm} 없음 — 정규화 단계 건너뜀", file=sys.stderr)
        return
    print("[정규화] normalize_train_test.py 실행 …")
    r = subprocess.run(
        [sys.executable, str(norm)],
        cwd=str(SCRIPT_DIR),
        check=False,
    )
    if r.returncode != 0:
        raise SystemExit(f"normalize_train_test.py 실패 (exit {r.returncode})")


def main() -> None:
    p = argparse.ArgumentParser(
        description="train·test output CSV → ArangoDB (split별 DB 권장)",
    )
    p.add_argument(
        "--train-output-dir",
        type=Path,
        default=DEFAULT_TRAIN_OUT,
        help="train 그래프 CSV 디렉터리 (기본: train_dataset/output)",
    )
    p.add_argument(
        "--test-output-dir",
        type=Path,
        default=DEFAULT_TEST_OUT,
        help="test 그래프 CSV 디렉터리 (기본: test_dataset/output)",
    )
    p.add_argument(
        "--train-database",
        type=str,
        default=os.environ.get("ARANGO_TRAIN_DATABASE", DEFAULT_TRAIN_DB),
        help=f"train 적재 DB (기본: {DEFAULT_TRAIN_DB} 또는 ARANGO_TRAIN_DATABASE)",
    )
    p.add_argument(
        "--test-database",
        type=str,
        default=os.environ.get("ARANGO_TEST_DATABASE", DEFAULT_TEST_DB),
        help=f"test 적재 DB (기본: {DEFAULT_TEST_DB} 또는 ARANGO_TEST_DATABASE)",
    )
    p.add_argument(
        "--only",
        choices=("train", "test", "both"),
        default="both",
        help="적재할 split",
    )
    p.add_argument(
        "--normalize-first",
        action="store_true",
        help="먼저 normalize_train_test.py 를 실행해 output/*.csv 생성",
    )
    p.add_argument(
        "--append",
        action="store_true",
        help="컬렉션 truncate 안 함 (같은 DB에 덮어쓰기만)",
    )
    p.add_argument("--batch", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.normalize_first:
        _maybe_normalize_first()

    jobs: list[tuple[str, Path, str]] = []
    if args.only in ("train", "both"):
        jobs.append(("train", args.train_output_dir.resolve(), args.train_database))
    if args.only in ("test", "both"):
        jobs.append(("test", args.test_output_dir.resolve(), args.test_database))

    for label, out_dir, db_name in jobs:
        print(f"\n=== [{label}] → Arango DB {db_name!r} ===")
        print(f"    CSV 경로: {out_dir}")
        run_import(
            out_dir,
            truncate=not args.append,
            batch=args.batch,
            dry_run=args.dry_run,
            database=db_name,
        )

    if not args.dry_run:
        print(
            "\n완료. Arango 웹 UI에서 DB를 미리 만들어 두었는지 확인하세요. "
            "langchain_graph_qa / 백엔드는 ARANGO_DATABASE 를 "
            f"학습 시 {args.train_database!r}, 평가 시 {args.test_database!r} 등으로 맞춥니다."
        )


if __name__ == "__main__":
    main()
