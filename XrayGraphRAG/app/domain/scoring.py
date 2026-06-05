"""유사 case -> disease score(weighted voting)."""
from __future__ import annotations

from typing import Dict, List, Tuple

from app.models.schemas import PredictedDisease, SimilarCase


EXCLUDED_DISEASE_TAGS = {"no_finding", "support_devices"}


def is_supported_disease_tag(tag: str | None) -> bool:
    if tag is None:
        return False
    return tag.strip().lower() not in EXCLUDED_DISEASE_TAGS


def case_weight(c: SimilarCase, current_view: str | None, current_model_version: str | None) -> float:
    """case_weight: maskQuality / imageQuality / view 일치 / modelVersion 일치 등 반영."""
    w = 1.0
    quality = (c.roiStats or {}).get("__quality__")
    if isinstance(quality, dict):
        w *= float(quality.get("maskQuality", 1.0))
        w *= float(quality.get("imageQuality", 1.0))
        if quality.get("artifactSuspected"):
            w *= 0.7
    return max(0.05, min(1.5, w))


def aggregate_disease_scores(
    similar_cases: List[SimilarCase],
    current_view: str | None = None,
    current_model_version: str | None = None,
) -> List[PredictedDisease]:
    """top-k similarity * case_weight 합산 -> 정규화."""
    raw: Dict[str, Tuple[float, int]] = {}
    for c in similar_cases:
        w = case_weight(c, current_view, current_model_version)
        contribution = max(0.0, c.similarity) * w
        for d in c.diseaseTags or []:
            if not is_supported_disease_tag(d):
                continue
            cur_score, cur_n = raw.get(d, (0.0, 0))
            raw[d] = (cur_score + contribution, cur_n + 1)

    if not raw:
        return []

    total = sum(v for v, _ in raw.values()) or 1.0
    out: List[PredictedDisease] = []
    for d, (s, n) in raw.items():
        out.append(
            PredictedDisease(
                disease=d,
                score=float(s / total),
                supportCases=int(n),
                reason="유사 사례 기반 weighted voting 결과",
            )
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out


def merge_similarity(
    global_results: List[SimilarCase],
    roi_results: Dict[str, List[SimilarCase]],
    weights: Dict[str, float],
) -> List[SimilarCase]:
    """caseId 기준 merge. score = sum(weight[r] * sim_r). 누락된 ROI는 0으로 둔다."""
    bag: Dict[str, Dict[str, float]] = {}
    cache: Dict[str, SimilarCase] = {}

    for c in global_results:
        bag.setdefault(c.caseId, {})["global"] = c.similarity
        cache.setdefault(c.caseId, c)

    for roi_name, results in roi_results.items():
        for c in results:
            bag.setdefault(c.caseId, {})[roi_name] = c.similarity
            cache.setdefault(c.caseId, c)

    merged: List[SimilarCase] = []
    for cid, sims in bag.items():
        score = 0.0
        for k, w in weights.items():
            score += sims.get(k, 0.0) * w
        base = cache[cid]
        merged.append(
            SimilarCase(
                caseId=cid,
                similarity=float(score),
                diseaseTags=[d for d in base.diseaseTags if is_supported_disease_tag(d)],
                findingTags=base.findingTags,
                roiStats=base.roiStats,
                imagePath=base.imagePath,
                heatmapPath=base.heatmapPath,
            )
        )
    merged.sort(key=lambda x: x.similarity, reverse=True)
    return merged


def adaptive_weights(roi_severity: Dict[str, str]) -> Dict[str, float]:
    """현재 case에서 severity가 high인 ROI의 가중치를 더 높인다.

    Default: global=0.50, right_lung=0.20, left_lung=0.20, heart=0.10
    high인 ROI가 1개면 0.40 / 0.35 / 0.15 / 0.10 식으로 재배분(합=1.0).
    """
    base = {"global": 0.50, "right_lung": 0.20, "left_lung": 0.20, "heart": 0.10}
    highs = [k for k in ("right_lung", "left_lung", "heart") if roi_severity.get(k) == "high"]
    if not highs:
        return base
    if len(highs) == 1:
        target = highs[0]
        new = {"global": 0.40, "right_lung": 0.15, "left_lung": 0.15, "heart": 0.10}
        new[target] = 0.35
        return new
    # 2개 이상이면 global을 줄이고 high끼리 배분
    new = {"global": 0.30}
    share = 0.70 / len(highs)
    for k in ("right_lung", "left_lung", "heart"):
        new[k] = share if k in highs else 0.05
    s = sum(new.values())
    return {k: v / s for k, v in new.items()}
