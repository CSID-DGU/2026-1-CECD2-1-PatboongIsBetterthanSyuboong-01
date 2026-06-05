"""Leave-One-Out (LOO) retrieval / disease prediction 평가 스크립트.

ArangoDB 에 등록된 모든 케이스를 대상으로:
  1) 각 케이스의 globalErrorEmbedding(또는 weighted ROI 합성 임베딩)을 query 로 두고
     자기 자신을 제외한 나머지 케이스에서 vector similarity search 를 수행.
  2) 멀티라벨 retrieval 메트릭(Hit@k / Precision@k / MRR / mAP) 계산.
  3) top-k weighted voting 으로 predicted disease 를 산출하고 top-1 / top-3 anymatch 정확도와
     per-disease recall 을 계산.
  4) ROI severity 분포 / finding tag 분포 통계 함께 산출.
  5) JSON 결과 + 사람이 읽을 수 있는 Markdown 보고서를 storage/eval/<timestamp>/ 에 저장.

설계 메모
- LOO 는 별도 holdout 셋 없이 dataset 내부에서 평가하는 표준 방식.
- multi-label 환경에서 "relevance" 는 query 의 disease 집합과 retrieved case 의 disease 집합의
  교집합이 비어있지 않은 경우로 정의.
- ROI별 임베딩까지 합산한 final similarity 도 옵션으로 평가 가능 (--use-roi).
- view / modelVersion 이 다른 케이스끼리 비교하지 않도록 필터링.
- LOO 결과는 기존 fallback AQL 로 매번 호출하면 N^2 으로 느려지므로 in-memory 행렬 곱으로 처리.
  (운영 path 검증은 별도 smoke_infer.py 가 담당.)

실행:
  $env:PYTHONIOENCODING="utf-8"
  $env:ARANGO_PASSWORD="..."
  python scripts/eval_retrieval.py
  python scripts/eval_retrieval.py --use-roi --view AP
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set


def _setup_io() -> None:
    for s in ("stdout", "stderr"):
        try:
            getattr(sys, s).reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    here = Path(__file__).resolve()
    if str(here.parent.parent) not in sys.path:
        sys.path.insert(0, str(here.parent.parent))


_setup_io()

import numpy as np  # noqa: E402

from app.api.dependencies import get_container  # noqa: E402
from app.config import get_settings  # noqa: E402


def _l2_normalize(x: np.ndarray, axis: int = 1, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(x, axis=axis, keepdims=True)
    return x / (n + eps)


def _ks() -> List[int]:
    return [1, 3, 5, 10, 20]


def _build_similarity(
    embeddings: Dict[str, np.ndarray],
    weights: Dict[str, float],
) -> np.ndarray:
    """ROI별 코사인 유사도를 가중합한 최종 similarity 행렬."""
    sim_total: Optional[np.ndarray] = None
    total_w = 0.0
    for k, w in weights.items():
        emb = embeddings.get(k)
        if emb is None:
            continue
        emb = _l2_normalize(emb)
        s = emb @ emb.T
        sim_total = s * w if sim_total is None else sim_total + s * w
        total_w += w
    assert sim_total is not None, "no embeddings available for similarity"
    return sim_total / max(total_w, 1e-8)


def _apply_filters(
    sim: np.ndarray,
    views: List[str],
    model_versions: List[str],
    *,
    self_neg: float = -np.inf,
) -> np.ndarray:
    """대각성분 제거(self) + view/modelVersion 일치 케이스만 비교."""
    n = sim.shape[0]
    out = sim.copy()
    np.fill_diagonal(out, self_neg)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if views[i] != views[j] or model_versions[i] != model_versions[j]:
                out[i, j] = self_neg
    return out


def _evaluate(
    *,
    sim: np.ndarray,
    labels: List[Set[str]],
    ks: Sequence[int] = tuple(_ks()),
    vote_top_k: int = 20,
) -> Dict[str, Any]:
    n = sim.shape[0]
    hit = {k: 0 for k in ks}
    prec = {k: 0.0 for k in ks}
    mrr_sum = 0.0
    ap_sum = 0.0
    top1_correct = 0
    top3_correct = 0
    per_disease = defaultdict(lambda: {"top1": 0, "top3": 0, "any_match_top3": 0, "n": 0})
    n_eval = 0
    n_no_label = 0

    # near-duplicate 모니터링 (sim ≥ 0.999)
    n_near_dup = 0

    for i in range(n):
        gt = labels[i]
        if not gt:
            n_no_label += 1
            continue
        n_eval += 1

        order = np.argsort(-sim[i])
        # 유효(=finite) similarity 값만 유지
        valid_order = [j for j in order if np.isfinite(sim[i, j])]
        if not valid_order:
            continue
        if sim[i, valid_order[0]] >= 0.999:
            n_near_dup += 1

        relevances = [bool(labels[j] & gt) for j in valid_order]

        for k in ks:
            rel_k = relevances[:k]
            if not rel_k:
                continue
            hit[k] += int(any(rel_k))
            prec[k] += sum(rel_k) / k

        # MRR: 첫 relevant 순위의 역수
        rr = 0.0
        for r, rel in enumerate(relevances, start=1):
            if rel:
                rr = 1.0 / r
                break
        mrr_sum += rr

        # mAP: standard average precision
        n_rel = sum(relevances)
        if n_rel > 0:
            seen = 0
            ap = 0.0
            for r, rel in enumerate(relevances, start=1):
                if rel:
                    seen += 1
                    ap += seen / r
            ap_sum += ap / n_rel

        # weighted voting
        top_k_idx = valid_order[:vote_top_k]
        scores: Dict[str, float] = defaultdict(float)
        for j in top_k_idx:
            s = float(sim[i, j])
            if s <= 0:
                continue
            for d in labels[j]:
                scores[d] += s
        ranking = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        pred_top1 = {ranking[0][0]} if ranking else set()
        pred_top3 = {d for d, _ in ranking[:3]}

        if pred_top1 & gt:
            top1_correct += 1
        if pred_top3 & gt:
            top3_correct += 1

        for d in gt:
            per_disease[d]["n"] += 1
            if d in pred_top1:
                per_disease[d]["top1"] += 1
            if d in pred_top3:
                per_disease[d]["top3"] += 1
            if pred_top3 & gt:
                per_disease[d]["any_match_top3"] += 1

    denom = max(n_eval, 1)
    metrics: Dict[str, Any] = {
        "n_total_cases": int(n),
        "n_evaluated": int(n_eval),
        "n_no_finding": int(n_no_label),
        "n_near_duplicates": int(n_near_dup),
        "hit_at_k": {str(k): hit[k] / denom for k in ks},
        "precision_at_k": {str(k): prec[k] / denom for k in ks},
        "mrr": mrr_sum / denom,
        "map": ap_sum / denom,
        "top1_accuracy_any_match": top1_correct / denom,
        "top3_accuracy_any_match": top3_correct / denom,
        "per_disease_recall": {
            d: {
                "n": v["n"],
                "top1": v["top1"] / max(v["n"], 1),
                "top3": v["top3"] / max(v["n"], 1),
            }
            for d, v in sorted(per_disease.items(), key=lambda kv: -kv[1]["n"])
        },
    }
    return metrics


# ---------- ROI severity / finding 분포 ----------
def _aggregate_population_stats(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    sev_dist: Dict[str, Counter[str]] = defaultdict(Counter)
    for c in cases:
        for roi, st in (c.get("roiStats") or {}).items():
            sev = st.get("severity", "low") if isinstance(st, dict) else "low"
            sev_dist[roi][sev] += 1
    finding_counter: Counter[str] = Counter()
    for c in cases:
        for f in c.get("findingTags") or []:
            finding_counter[f] += 1
    disease_counter: Counter[str] = Counter()
    for c in cases:
        for d in c.get("diseaseTags") or []:
            disease_counter[d] += 1
    view_counter: Counter[str] = Counter(c.get("view", "?") for c in cases)
    return {
        "roi_severity_distribution": {
            roi: dict(sorted(cnt.items())) for roi, cnt in sorted(sev_dist.items())
        },
        "finding_tag_distribution": dict(finding_counter.most_common()),
        "disease_distribution": dict(disease_counter.most_common()),
        "view_distribution": dict(view_counter.most_common()),
    }


# ---------- Markdown 리포트 ----------
def _md_report(meta: Dict[str, Any], metrics: Dict[str, Any], pop: Dict[str, Any]) -> str:
    L: List[str] = []

    L.append("# X-ray Retrieval Evaluation Report")
    L.append("")
    L.append("> 본 보고서는 분류 모델 없이 reconstruction error embedding 의 vector similarity")
    L.append("> 를 통해 disease 후보를 추론하는 시스템에 대한 Leave-One-Out (LOO) 평가 결과입니다.")
    L.append("> **의학적 진단 도구가 아닙니다.**")
    L.append("")
    L.append("## 1. 실행 메타")
    L.append("")
    L.append("| key | value |")
    L.append("| --- | --- |")
    for k, v in meta.items():
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## 2. 데이터 분포")
    L.append("")
    L.append(f"- 등록된 케이스: **{metrics['n_total_cases']}**")
    L.append(f"- 평가 대상(라벨 있음): **{metrics['n_evaluated']}**")
    L.append(f"- No Finding/라벨 없음 제외: {metrics['n_no_finding']}")
    L.append(f"- top-1 similarity ≥ 0.999 인 query 수: {metrics['n_near_duplicates']} (중복/매우 유사 사례 영향)")
    L.append("")
    L.append("### 2.1 disease 분포(등록 기준)")
    L.append("")
    L.append("| disease | count |")
    L.append("| --- | ---: |")
    for d, c in pop["disease_distribution"].items():
        L.append(f"| {d} | {c} |")
    L.append("")
    L.append("### 2.2 view 분포")
    L.append("")
    L.append("| view | count |")
    L.append("| --- | ---: |")
    for v, c in pop["view_distribution"].items():
        L.append(f"| {v} | {c} |")
    L.append("")

    L.append("## 3. Retrieval 메트릭 (multi-label)")
    L.append("")
    L.append("- *Relevance* 정의: query 의 disease 집합과 retrieved case 의 disease 집합 교집합 ≠ ∅")
    L.append("")
    L.append(f"- **MRR**: {metrics['mrr']:.4f}")
    L.append(f"- **mAP**: {metrics['map']:.4f}")
    L.append("")
    L.append("| k | Hit@k | Precision@k |")
    L.append("| ---: | ---: | ---: |")
    for k in [1, 3, 5, 10, 20]:
        L.append(f"| {k} | {metrics['hit_at_k'][str(k)]:.4f} | {metrics['precision_at_k'][str(k)]:.4f} |")
    L.append("")

    L.append("## 4. Disease prediction (weighted voting, top-K=20)")
    L.append("")
    L.append(f"- **Top-1 any-match accuracy**: {metrics['top1_accuracy_any_match']:.4f}")
    L.append(f"- **Top-3 any-match accuracy**: {metrics['top3_accuracy_any_match']:.4f}")
    L.append("")
    L.append("### 4.1 Per-disease recall")
    L.append("")
    L.append("| disease | n | recall@1 | recall@3 |")
    L.append("| --- | ---: | ---: | ---: |")
    for d, v in metrics["per_disease_recall"].items():
        L.append(f"| {d} | {v['n']} | {v['top1']:.3f} | {v['top3']:.3f} |")
    L.append("")

    L.append("## 5. ROI severity 분포 (모든 등록 케이스 기준)")
    L.append("")
    L.append("| roi | low | medium | high |")
    L.append("| --- | ---: | ---: | ---: |")
    for roi, dist in pop["roi_severity_distribution"].items():
        L.append(f"| {roi} | {dist.get('low', 0)} | {dist.get('medium', 0)} | {dist.get('high', 0)} |")
    L.append("")

    L.append("## 6. 자동 생성된 finding tag 분포")
    L.append("")
    if pop["finding_tag_distribution"]:
        L.append("| finding | count |")
        L.append("| --- | ---: |")
        for f, c in pop["finding_tag_distribution"].items():
            L.append(f"| {f} | {c} |")
    else:
        L.append("(자동 finding tag 가 생성된 케이스 없음. ROI severity가 모두 low 였거나 임계값을 조정하면 됩니다.)")
    L.append("")

    L.append("## 7. 한계점 / 해석 가이드")
    L.append("")
    L.append("- LOO 평가이며, holdout 셋이 아닙니다. 같은 분포 안에서의 retrieval 능력만 측정합니다.")
    L.append("- ROI mask 가 mock(타원 휴리스틱)이라 의학적 정확도가 떨어집니다. 실제 segmentation 모델로")
    L.append("  교체 시 ROI 통계와 finding tag 신뢰도가 향상될 수 있습니다.")
    L.append("- CheXpert 라벨 자체가 multi-label 이고 분포가 매우 불균형합니다(예: pneumothorax, lung_lesion).")
    L.append("  per-disease 의 n 값이 작은 라벨은 통계적 유의성이 낮습니다.")
    L.append("- top-1 similarity ≥ 0.999 인 케이스는 등록 시 중복 또는 거의 동일한 영상이 있다는 의미이며,")
    L.append("  실제 운영에서는 dedupe 로직이 필요합니다.")
    L.append("- **의학적 진단을 대체하지 않습니다.** 본 결과는 reconstruction error pattern 기반의")
    L.append("  유사 사례 검색 능력을 정량화한 것일 뿐입니다.")
    L.append("")
    return "\n".join(L)


# ---------- 메인 ----------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-roi", action="store_true",
                        help="global + ROI 가중합 similarity 사용 (default: global only)")
    parser.add_argument("--view", default=None,
                        help="이 view 만 평가 대상 (예: AP, PA). 미지정 시 모든 view")
    parser.add_argument("--out", default=None,
                        help="출력 디렉터리 (default: storage/eval/<timestamp>)")
    args = parser.parse_args()

    settings = get_settings()
    container = get_container()
    db = container.db

    print(f"[arango] {settings.ARANGO_URL} db={settings.ARANGO_DB_NAME}")
    cursor = db.aql.execute(
        """
        FOR c IN xray_cases
          FILTER (@view == null OR c.view == @view)
          RETURN c
        """,
        bind_vars={"view": args.view},
    )
    cases: List[Dict[str, Any]] = list(cursor)
    n = len(cases)
    print(f"[load] cases: {n}")
    if n == 0:
        print("[fail] no cases registered. seed_chexpert.py 로 먼저 등록하세요.")
        return 2

    keys = [c["_key"] for c in cases]
    labels = [set(c.get("diseaseTags") or []) for c in cases]
    views = [c.get("view") or "?" for c in cases]
    model_versions = [c.get("modelVersion") or "?" for c in cases]

    embeddings: Dict[str, np.ndarray] = {}
    embeddings["global"] = np.array(
        [c["globalErrorEmbedding"] for c in cases], dtype=np.float32
    )
    if args.use_roi:
        for k, field in (
            ("right_lung", "rightLungErrorEmbedding"),
            ("left_lung", "leftLungErrorEmbedding"),
            ("heart", "heartErrorEmbedding"),
        ):
            embeddings[k] = np.array([c[field] for c in cases], dtype=np.float32)
        weights = {"global": 0.5, "right_lung": 0.2, "left_lung": 0.2, "heart": 0.1}
    else:
        weights = {"global": 1.0}

    sim = _build_similarity(embeddings, weights)
    sim = _apply_filters(sim, views, model_versions)

    print(f"[compute] similarity matrix shape={sim.shape}, weights={weights}")
    metrics = _evaluate(sim=sim, labels=labels)
    pop = _aggregate_population_stats(cases)

    out_dir = Path(args.out) if args.out else (
        settings.STORAGE_DIR / "eval" / time.strftime("%Y%m%d_%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model_version": settings.MODEL_VERSION,
        "embedding_version": settings.EMBEDDING_VERSION,
        "embedding_dim": settings.EMBEDDING_DIM,
        "similarity_weights": json.dumps(weights),
        "view_filter": args.view or "(all)",
    }

    (out_dir / "metrics.json").write_text(
        json.dumps({"meta": meta, "metrics": metrics, "population": pop}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(_md_report(meta, metrics, pop), encoding="utf-8")
    print(f"[done] saved: {out_dir}")
    print(f"  - metrics.json")
    print(f"  - report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
