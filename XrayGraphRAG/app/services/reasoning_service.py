"""유사 case + 그래프 traversal 결과를 종합해 disease/finding 후보를 만든다."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.db.repositories import CaseRepository
from app.domain.findings import derive_finding_tags  # noqa: F401  (외부 사용 호환)
from app.domain.scoring import aggregate_disease_scores
from app.domain.uncertainty import assess_uncertainty
from app.config import Settings
from app.models.schemas import (
    NotableFinding,
    PredictedDisease,
    Quality,
    ROIStats,
    SimilarCase,
    Uncertainty,
)


class ReasoningService:
    def __init__(self, repo: CaseRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def reason(
        self,
        similar_cases: List[SimilarCase],
        current_roi_stats: Dict[str, ROIStats],
        quality: Quality,
        view: str | None,
        model_version: str | None,
    ) -> Dict[str, Any]:
        diseases = aggregate_disease_scores(
            similar_cases, current_view=view, current_model_version=model_version
        )
        diseases = self._enrich_disease_reasons(diseases, similar_cases, current_roi_stats)

        notable = self._aggregate_findings(similar_cases, current_roi_stats)
        uncertainty = assess_uncertainty(similar_cases, diseases, quality, self.settings)

        graph_evidence = self.repo.graph_traversal([c.caseId for c in similar_cases[:5]])

        return {
            "predictedDiseases": diseases,
            "notableFindings": notable,
            "uncertainty": uncertainty,
            "graphEvidence": _summarize_graph(graph_evidence),
        }

    def _aggregate_findings(
        self,
        similar_cases: List[SimilarCase],
        current_roi_stats: Dict[str, ROIStats],
    ) -> List[NotableFinding]:
        if not similar_cases:
            return []
        n = len(similar_cases)
        counter: Counter[str] = Counter()
        for c in similar_cases:
            for t in c.findingTags or []:
                counter[t] += 1

        out: List[NotableFinding] = []
        for tag, cnt in counter.most_common(10):
            freq = cnt / n
            evidence = self._evidence_for_finding(tag, current_roi_stats)
            out.append(
                NotableFinding(
                    finding=tag,
                    frequencyInSimilarCases=round(freq, 3),
                    currentCaseEvidence=evidence,
                )
            )
        return out

    def _evidence_for_finding(self, tag: str, roi_stats: Dict[str, ROIStats]) -> Dict[str, Any]:
        candidates = {
            "right_lung_high_error": "right_lung",
            "left_lung_high_error": "left_lung",
            "right_lower_lung_high_error": "lower_right_lung",
            "right_upper_lung_high_error": "upper_right_lung",
            "left_lower_lung_high_error": "lower_left_lung",
            "left_upper_lung_high_error": "upper_left_lung",
            "pleural_region_high_error": "pleural_region",
            "cardiac_region_high_error": "heart",
            "mediastinum_high_error": "mediastinum",
            "bilateral_diffuse_error": "full_lung",
        }
        roi_name = candidates.get(tag)
        if not roi_name or roi_name not in roi_stats:
            return {}
        s = roi_stats[roi_name]
        return {
            "roi": roi_name,
            "p95Error": round(s.p95Error, 3),
            "meanError": round(s.meanError, 3),
            "areaRatio": round(s.areaRatio, 3),
            "severity": s.severity,
        }

    def _enrich_disease_reasons(
        self,
        diseases: List[PredictedDisease],
        similar_cases: List[SimilarCase],
        roi_stats: Dict[str, ROIStats],
    ) -> List[PredictedDisease]:
        if not diseases:
            return diseases
        # ROI severity 정렬 -> 가장 두드러진 ROI 식별
        sorted_rois = sorted(
            ((k, v) for k, v in roi_stats.items() if k in ("right_lung", "left_lung", "heart", "lower_right_lung", "lower_left_lung")),
            key=lambda kv: kv[1].p95Error,
            reverse=True,
        )
        most_roi = sorted_rois[0][0] if sorted_rois else None

        enriched: List[PredictedDisease] = []
        for d in diseases:
            support = sum(1 for c in similar_cases if d.disease in (c.diseaseTags or []))
            roi_clause = f", 현재 영상은 {most_roi} 영역의 reconstruction error가 두드러집니다." if most_roi else ""
            reason = (
                f"Top-{len(similar_cases)} 유사 사례 중 {support}개가 '{d.disease}' 태그를 보유"
                f"{roi_clause}"
            )
            enriched.append(
                PredictedDisease(
                    disease=d.disease,
                    score=round(d.score, 3),
                    supportCases=support,
                    reason=reason,
                )
            )
        return enriched


def _summarize_graph(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    diseases: Counter[str] = Counter()
    findings: Counter[str] = Counter()
    rois: Counter[str] = Counter()
    for r in rows:
        v = r.get("vertex") or {}
        coll = (v.get("_id") or "").split("/")[0]
        if coll == "diseases":
            diseases[v.get("_key", "")] += 1
        elif coll == "findings":
            findings[v.get("_key", "")] += 1
        elif coll == "rois":
            rois[v.get("_key", "")] += 1
    return {
        "diseases": [{"key": k, "count": c} for k, c in diseases.most_common(10)],
        "findings": [{"key": k, "count": c} for k, c in findings.most_common(10)],
        "rois": [{"key": k, "count": c} for k, c in rois.most_common(10)],
    }
