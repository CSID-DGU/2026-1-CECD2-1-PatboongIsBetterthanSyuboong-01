"""Agent: retrieval/graph 결과 외 내용을 임의로 만들지 않는 template-based 설명 생성기.

LLM이 연결되어 있지 않아도 동작한다. 추후 LLM을 붙이려면 build_prompt() 결과를
LLM에 그대로 넘기고, retrieval evidence 외 hallucination을 막도록 system prompt에
제약을 두면 된다.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.config import Settings
from app.models.schemas import (
    NotableFinding,
    PredictedDisease,
    ROIStats,
    SimilarCase,
    Uncertainty,
)


class AgentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def explain(
        self,
        *,
        diseases: List[PredictedDisease],
        notable_findings: List[NotableFinding],
        similar_cases: List[SimilarCase],
        roi_stats: Dict[str, ROIStats],
        uncertainty: Uncertainty,
        graph_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        confidence_level = _confidence_level(uncertainty.level)

        predicted_block: List[Dict[str, Any]] = []
        for d in diseases[:5]:
            evidence_lines = [
                f"Top-{len(similar_cases)} 유사 사례 중 {d.supportCases}개가 '{d.disease}' 태그를 보유합니다.",
            ]
            top_roi = _top_roi(roi_stats)
            if top_roi:
                evidence_lines.append(
                    f"현재 영상은 {top_roi[0]} ROI의 p95 reconstruction error={top_roi[1].p95Error:.3f}로 두드러집니다."
                )
            related_findings = [f.finding for f in notable_findings if f.frequencyInSimilarCases >= 0.3]
            if related_findings:
                evidence_lines.append(
                    "유사 사례 다수에서 다음 finding이 함께 나타납니다: " + ", ".join(related_findings[:3])
                )
            predicted_block.append({
                "name": d.disease,
                "score": d.score,
                "confidenceLevel": confidence_level,
                "evidence": evidence_lines,
            })

        notable_lines = [
            (
                f"{f.finding} (유사 사례 빈도={f.frequencyInSimilarCases:.0%}"
                f"{', 현재: ' + str(f.currentCaseEvidence) if f.currentCaseEvidence else ''})"
            )
            for f in notable_findings[:5]
        ]
        if not notable_lines and roi_stats:
            top_roi = _top_roi(roi_stats)
            if top_roi:
                notable_lines.append(
                    f"{top_roi[0]} ROI의 reconstruction error가 다른 영역보다 두드러집니다."
                )

        limitations = [
            "Reconstruction error는 촬영 품질, 환자 자세, 압박 정도, artifact 등에 영향을 받을 수 있습니다.",
            "이 결과는 영상의학 전문의의 판독을 대체하지 않습니다.",
            "본 시스템은 연구/프로토타입이며 의학적 확정 진단 도구가 아닙니다.",
        ]
        if uncertainty.reasons:
            limitations.append("Uncertainty 사유: " + "; ".join(uncertainty.reasons))

        return {
            "summary": (
                "이 결과는 진단이 아니라 reconstruction error pattern 기반의 유사 사례 검색 결과입니다."
            ),
            "predictedDiseases": predicted_block,
            "notableFindings": notable_lines,
            "similarCaseSummary": [
                {"caseId": c.caseId, "similarity": round(c.similarity, 3),
                 "diseaseTags": c.diseaseTags}
                for c in similar_cases[:5]
            ],
            "graphEvidence": graph_evidence,
            "uncertainty": {"level": uncertainty.level, "reasons": uncertainty.reasons},
            "limitations": limitations,
            "warning": self.settings.SAFETY_NOTICE,
        }


def _confidence_level(uncertainty_level: str) -> str:
    return {"low": "moderate-high", "medium": "moderate", "high": "low"}.get(uncertainty_level, "low")


def _top_roi(roi_stats: Dict[str, ROIStats]):
    if not roi_stats:
        return None
    items = list(roi_stats.items())
    items.sort(key=lambda kv: kv[1].p95Error, reverse=True)
    return items[0]
