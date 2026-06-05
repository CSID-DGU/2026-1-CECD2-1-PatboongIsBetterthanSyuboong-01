#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3분할(train/calibration/test) 기반 처방 적절성 평가기.

평가 점수:
  S_freq(D, M) = Count(D ∩ M) / Count(D)
  S_similarity(V, M) = 유사 방문군(진단코드 조합)에서 약물 M 사용 빈도(가중)
  Score_total = w1 * S_freq + w2 * S_similarity

기본 동작:
- train.csv 로 통계/유사도 기준(에이전트 근거)을 구축
- calibration.csv 로 w1/w2/threshold 를 튜닝(선택)
- test.csv(또는 특정 환자)의 실제 처방 라인을 최종 점수화
- 결과를 CSV 로 저장
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class VisitRecord:
    visit_id: str
    diagnosis_codes: set[str]
    medications: set[str]


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: _clean(v) for k, v in row.items()} for row in reader]


def _build_visits(rows: Iterable[dict[str, str]]) -> dict[str, VisitRecord]:
    dx_by_visit: dict[str, set[str]] = defaultdict(set)
    med_by_visit: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        visit = row.get("내원번호", "")
        dx = row.get("상병코드", "")
        med = row.get("처방코드", "")
        if not visit:
            continue
        if dx:
            dx_by_visit[visit].add(dx)
        if med:
            med_by_visit[visit].add(med)

    out: dict[str, VisitRecord] = {}
    for visit_id in set(dx_by_visit.keys()) | set(med_by_visit.keys()):
        out[visit_id] = VisitRecord(
            visit_id=visit_id,
            diagnosis_codes=dx_by_visit.get(visit_id, set()),
            medications=med_by_visit.get(visit_id, set()),
        )
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return min(values)
    if q >= 1:
        return max(values)
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def build_train_stats(
    train_visits: dict[str, VisitRecord],
) -> tuple[Counter[str], Counter[tuple[str, str]], list[VisitRecord]]:
    """진단 방문수 Count(D), 진단-약물 동시발생 방문수 Count(D∩M) 계산."""
    diagnosis_visit_count: Counter[str] = Counter()
    diagnosis_med_visit_count: Counter[tuple[str, str]] = Counter()

    for visit in train_visits.values():
        for dx in visit.diagnosis_codes:
            diagnosis_visit_count[dx] += 1
            for med in visit.medications:
                diagnosis_med_visit_count[(dx, med)] += 1

    return diagnosis_visit_count, diagnosis_med_visit_count, list(train_visits.values())


def s_freq_for_med(
    med_code: str,
    diagnosis_codes: set[str],
    diagnosis_visit_count: Counter[str],
    diagnosis_med_visit_count: Counter[tuple[str, str]],
) -> tuple[float, str]:
    """
    한 방문(복수 진단)에서 약물 M의 S_freq를 계산.
    - 진단별 S_freq 중 최대값을 해당 약물의 대표값으로 사용
    """
    best_score = 0.0
    best_dx = ""
    for dx in diagnosis_codes:
        denom = diagnosis_visit_count.get(dx, 0)
        if denom <= 0:
            continue
        score = diagnosis_med_visit_count.get((dx, med_code), 0) / denom
        if score > best_score:
            best_score = score
            best_dx = dx
    return best_score, best_dx


def s_similarity_for_med(
    med_code: str,
    target_dx_set: set[str],
    train_visit_records: list[VisitRecord],
) -> tuple[float, int]:
    """
    유사 방문군 기반 점수:
      sum(sim(v,u) * I(med in u)) / sum(sim(v,u))
    """
    weighted_hit = 0.0
    weighted_total = 0.0
    neighbor_count = 0

    for v in train_visit_records:
        sim = _jaccard(target_dx_set, v.diagnosis_codes)
        if sim <= 0:
            continue
        neighbor_count += 1
        weighted_total += sim
        if med_code in v.medications:
            weighted_hit += sim

    if weighted_total <= 0:
        return 0.0, 0
    return weighted_hit / weighted_total, neighbor_count


def _pairwise_auc_like(pos_scores: list[float], neg_scores: list[float]) -> float:
    if not pos_scores or not neg_scores:
        return 0.0
    combined: list[tuple[float, int]] = [(s, 1) for s in pos_scores] + [(s, 0) for s in neg_scores]
    combined.sort(key=lambda x: x[0])

    rank_sum_pos = 0.0
    i = 0
    n = len(combined)
    # tie를 평균 rank로 처리 (Mann-Whitney U 기반 AUC)
    while i < n:
        j = i + 1
        while j < n and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0  # rank는 1-indexed
        for k in range(i, j):
            if combined[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j

    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    u = rank_sum_pos - (n_pos * (n_pos + 1) / 2.0)
    return u / (n_pos * n_neg)


def auto_calibrate(
    fit_rows: list[dict[str, str]],
    train_visits: dict[str, VisitRecord],
    calibration_rows: list[dict[str, str]],
    negatives_per_positive: int,
    target_recall: float,
    seed: int,
) -> tuple[float, float, float, float, dict[str, float]]:
    """
    양성 데이터만 있는 상황에서 pseudo-negative 샘플링으로 가중치/임계값을 자동 보정.

    - w1/w2: calibration 점수로 positive vs pseudo-negative 분리(AUC-like) 최대화
    - decision_threshold: 양성 calibration 점수 분포의 (1-target_recall) 분위수
    - rare_freq_threshold: 양성 calibration S_freq 5% 분위수
    """
    rng = random.Random(seed)
    med_vocab = sorted({r.get("처방코드", "") for r in fit_rows if r.get("처방코드", "")})
    if not med_vocab:
        return 0.6, 0.4, 0.01, 0.4, {"auc_like": 0.0, "calib_rows": 0}

    calibration_visits = _build_visits(calibration_rows)
    fit_dx_cnt, fit_dx_med_cnt, fit_visit_list = build_train_stats(train_visits)
    candidate_w1 = [x / 10.0 for x in range(0, 11)]  # 0.0 ... 1.0
    best_w1 = 0.6
    best_auc = -1.0
    best_pos_scores: list[float] = []
    best_pos_freq_scores: list[float] = []

    for w1 in candidate_w1:
        w2 = 1.0 - w1
        pos_scores: list[float] = []
        neg_scores: list[float] = []
        pos_freq_scores: list[float] = []

        for _, vrec in calibration_visits.items():
            dx_set = vrec.diagnosis_codes
            if not dx_set:
                continue
            pos_meds = list(vrec.medications)
            if not pos_meds:
                continue
            for med in pos_meds:
                sf, _ = s_freq_for_med(med, dx_set, fit_dx_cnt, fit_dx_med_cnt)
                ss, _ = s_similarity_for_med(med, dx_set, fit_visit_list)
                pos_freq_scores.append(sf)
                pos_scores.append(w1 * sf + w2 * ss)

                neg_pool = [m for m in med_vocab if m not in vrec.medications]
                if not neg_pool:
                    continue
                k = min(negatives_per_positive, len(neg_pool))
                sampled_neg = rng.sample(neg_pool, k)
                for nmed in sampled_neg:
                    nsf, _ = s_freq_for_med(nmed, dx_set, fit_dx_cnt, fit_dx_med_cnt)
                    nss, _ = s_similarity_for_med(nmed, dx_set, fit_visit_list)
                    neg_scores.append(w1 * nsf + w2 * nss)

        auc = _pairwise_auc_like(pos_scores, neg_scores)
        if auc > best_auc:
            best_auc = auc
            best_w1 = w1
            best_pos_scores = pos_scores
            best_pos_freq_scores = pos_freq_scores

    best_w2 = 1.0 - best_w1
    threshold_q = max(0.0, min(1.0, 1.0 - target_recall))
    nz_total_scores = [x for x in best_pos_scores if x > 0]
    nz_freq_scores = [x for x in best_pos_freq_scores if x > 0]
    decision_threshold = (
        _quantile(nz_total_scores, threshold_q)
        if nz_total_scores
        else (_quantile(best_pos_scores, threshold_q) if best_pos_scores else 0.4)
    )
    rare_freq_threshold = (
        _quantile(nz_freq_scores, 0.05)
        if nz_freq_scores
        else (_quantile(best_pos_freq_scores, 0.05) if best_pos_freq_scores else 0.01)
    )
    metrics = {
        "auc_like": best_auc if best_auc >= 0 else 0.0,
        "calib_rows": float(len(best_pos_scores)),
    }
    return best_w1, best_w2, rare_freq_threshold, decision_threshold, metrics


def evaluate_rows(
    test_rows: list[dict[str, str]],
    train_visits: dict[str, VisitRecord],
    w1: float,
    w2: float,
    rare_freq_threshold: float,
    decision_threshold: float,
    calibration_auc_like: float | None = None,
    calibration_rows_count: int | None = None,
) -> list[dict[str, str]]:
    train_dx_visit_count, train_dx_med_count, train_visit_list = build_train_stats(train_visits)
    test_visits = _build_visits(test_rows)

    out_rows: list[dict[str, str]] = []
    for row in test_rows:
        visit_id = row.get("내원번호", "")
        med_code = row.get("처방코드", "")
        visit = test_visits.get(visit_id)
        dx_set = visit.diagnosis_codes if visit else set()

        s_freq, anchor_dx = s_freq_for_med(
            med_code,
            dx_set,
            train_dx_visit_count,
            train_dx_med_count,
        )
        s_sim, neighbor_count = s_similarity_for_med(
            med_code=med_code,
            target_dx_set=dx_set,
            train_visit_records=train_visit_list,
        )
        score_total = (w1 * s_freq) + (w2 * s_sim)
        freq_flag = "이례 처방(희귀)" if s_freq < rare_freq_threshold else "일반 범주"
        if s_freq == 0.0 and s_sim == 0.0:
            decision = "데이터 부족(근거 없음)"
        else:
            decision = "적절" if score_total >= decision_threshold else "재검토 필요"

        enriched = dict(row)
        enriched["anchor_diagnosis"] = anchor_dx or ""
        enriched["s_freq"] = f"{s_freq:.6f}"
        enriched["s_similarity"] = f"{s_sim:.6f}"
        enriched["score_total"] = f"{score_total:.6f}"
        enriched["similar_neighbor_count"] = str(neighbor_count)
        enriched["freq_flag"] = freq_flag
        enriched["decision"] = decision
        enriched["eval_w1"] = f"{w1:.6f}"
        enriched["eval_w2"] = f"{w2:.6f}"
        enriched["eval_rare_freq_threshold"] = f"{rare_freq_threshold:.6f}"
        enriched["eval_decision_threshold"] = f"{decision_threshold:.6f}"
        enriched["eval_calibration_auc_like"] = (
            f"{calibration_auc_like:.6f}" if calibration_auc_like is not None else ""
        )
        enriched["eval_calibration_rows"] = (
            str(calibration_rows_count) if calibration_rows_count is not None else ""
        )
        out_rows.append(enriched)
    return out_rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="처방 적절성 점수 평가 도구 (train/calibration/test CSV)")
    p.add_argument(
        "--train-csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data_normalize" / "train_dataset" / "train.csv",
        help="학습 통계 생성용 train CSV",
    )
    p.add_argument(
        "--test-csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data_normalize" / "test_dataset" / "test.csv",
        help="최종 평가 대상 test CSV",
    )
    p.add_argument(
        "--calibration-csv",
        type=Path,
        default=None,
        help="파라미터(w1/w2/threshold) 튜닝용 calibration CSV (--auto-calibrate 시 필수 권장)",
    )
    p.add_argument(
        "--patient-id",
        type=str,
        default="",
        help="내원번호 기준 특정 환자만 평가 (예: 530524451)",
    )
    p.add_argument("--w1", type=float, default=0.6, help="S_freq 가중치")
    p.add_argument("--w2", type=float, default=0.4, help="S_similarity 가중치")
    p.add_argument(
        "--auto-calibrate",
        action="store_true",
        help="train(근거) + calibration(튜닝)으로 w1/w2 및 임계값 자동 보정",
    )
    p.add_argument(
        "--negatives-per-positive",
        type=int,
        default=8,
        help="자동 보정 시 양성 1건당 pseudo-negative 샘플 수",
    )
    p.add_argument(
        "--target-recall",
        type=float,
        default=0.9,
        help="decision_threshold 자동 보정 목표 재현율(0~1)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="자동 보정 샘플링 시드",
    )
    p.add_argument(
        "--rare-freq-threshold",
        type=float,
        default=0.01,
        help="S_freq < 임계값이면 이례 처방으로 표기",
    )
    p.add_argument(
        "--decision-threshold",
        type=float,
        default=0.4,
        help="Score_total >= 임계값이면 '적절' 판정",
    )
    p.add_argument(
        "--output-csv",
        type=Path,
        default=Path(__file__).resolve().parent / "prescription_eval_report.csv",
        help="평가 결과 저장 경로",
    )
    return p.parse_args()


def _validate_weights(w1: float, w2: float) -> None:
    if w1 < 0 or w2 < 0:
        raise ValueError("w1, w2는 음수일 수 없습니다.")
    s = w1 + w2
    if abs(s - 1.0) > 1e-6:
        raise ValueError(f"w1 + w2 = 1 이어야 합니다. 현재 합: {s}")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            f.write("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("[요약] 평가 대상 데이터가 없습니다.")
        return
    n = len(rows)
    n_ok = sum(1 for r in rows if r.get("decision") == "적절")
    n_review = n - n_ok
    avg_total = sum(float(r["score_total"]) for r in rows) / n
    avg_freq = sum(float(r["s_freq"]) for r in rows) / n
    avg_sim = sum(float(r["s_similarity"]) for r in rows) / n
    print(
        "[요약] "
        f"총 {n}건 | 적절 {n_ok}건 | 재검토 {n_review}건 | "
        f"평균 score_total={avg_total:.4f}, s_freq={avg_freq:.4f}, s_similarity={avg_sim:.4f}"
    )


def main() -> None:
    args = parse_args()
    _validate_weights(args.w1, args.w2)

    if not args.train_csv.is_file():
        raise SystemExit(f"[오류] train CSV 없음: {args.train_csv}")
    if not args.test_csv.is_file():
        raise SystemExit(f"[오류] test CSV 없음: {args.test_csv}")

    train_rows = _read_rows(args.train_csv)
    test_rows = _read_rows(args.test_csv)
    calibration_rows: list[dict[str, str]] = []
    if args.calibration_csv:
        if not args.calibration_csv.is_file():
            raise SystemExit(f"[오류] calibration CSV 없음: {args.calibration_csv}")
        calibration_rows = _read_rows(args.calibration_csv)

    if args.patient_id:
        test_rows = [r for r in test_rows if r.get("내원번호") == args.patient_id]

    train_visits = _build_visits(train_rows)
    w1 = args.w1
    w2 = args.w2
    rare_freq_threshold = args.rare_freq_threshold
    decision_threshold = args.decision_threshold
    calib_metrics: dict[str, float] = {"auc_like": 0.0, "calib_rows": 0.0}

    if args.auto_calibrate:
        if not (0.0 < args.target_recall < 1.0):
            raise SystemExit("[오류] --target-recall 은 0~1 사이여야 합니다.")
        if args.negatives_per_positive < 1:
            raise SystemExit("[오류] --negatives-per-positive 는 1 이상이어야 합니다.")
        if not calibration_rows:
            raise SystemExit(
                "[오류] --auto-calibrate 사용 시 --calibration-csv 를 지정하세요. "
                "(train/test 누수 방지를 위해 calibration 전용 세트 필요)"
            )

        w1, w2, rare_freq_threshold, decision_threshold, calib_metrics = auto_calibrate(
            fit_rows=train_rows,
            train_visits=train_visits,
            calibration_rows=calibration_rows,
            negatives_per_positive=args.negatives_per_positive,
            target_recall=args.target_recall,
            seed=args.seed,
        )
        print(
            "[보정] "
            f"w1={w1:.2f}, w2={w2:.2f}, "
            f"rare_freq_threshold={rare_freq_threshold:.6f}, "
            f"decision_threshold={decision_threshold:.6f}, "
            f"auc_like={calib_metrics['auc_like']:.4f}, "
            f"calib_rows={int(calib_metrics['calib_rows'])}"
        )

    calib_auc = calib_metrics["auc_like"] if args.auto_calibrate else None
    calib_rows_count = int(calib_metrics["calib_rows"]) if args.auto_calibrate else None
    evaluated = evaluate_rows(
        test_rows=test_rows,
        train_visits=train_visits,
        w1=w1,
        w2=w2,
        rare_freq_threshold=rare_freq_threshold,
        decision_threshold=decision_threshold,
        calibration_auc_like=calib_auc,
        calibration_rows_count=calib_rows_count,
    )
    _write_csv(args.output_csv, evaluated)

    print(f"[완료] 결과 저장: {args.output_csv}")
    _print_summary(evaluated)


if __name__ == "__main__":
    main()
