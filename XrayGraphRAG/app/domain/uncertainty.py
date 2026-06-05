"""불확실성 평가."""
from __future__ import annotations

from typing import List

from app.config import Settings
from app.models.schemas import PredictedDisease, Quality, SimilarCase, Uncertainty


def assess_uncertainty(
    similar_cases: List[SimilarCase],
    diseases: List[PredictedDisease],
    quality: Quality,
    settings: Settings,
) -> Uncertainty:
    reasons: List[str] = []
    level = "low"

    if not similar_cases:
        return Uncertainty(level="high", reasons=["No similar cases found"])

    top1 = similar_cases[0].similarity
    avg = sum(c.similarity for c in similar_cases) / max(1, len(similar_cases))

    if top1 < settings.UNCERT_HIGH_TOP1:
        reasons.append(f"Top-1 similarity({top1:.2f}) is below threshold({settings.UNCERT_HIGH_TOP1:.2f})")
        level = _bump(level, "high")

    if avg < settings.UNCERT_HIGH_TOP1 * 0.85:
        reasons.append(f"Average top-k similarity({avg:.2f}) is low")
        level = _bump(level, "medium")

    if len(diseases) >= 2:
        gap = diseases[0].score - diseases[1].score
        if gap < settings.UNCERT_MED_GAP:
            reasons.append(
                f"Top-1 disease score and Top-2 disease score are close (gap={gap:.2f})"
            )
            level = _bump(level, "medium")

    if len(similar_cases) < settings.UNCERT_MIN_CASES:
        reasons.append(f"Only {len(similar_cases)} similar cases found")
        level = _bump(level, "medium")

    if quality.maskQuality < 0.5:
        reasons.append("Mask quality is low")
        level = _bump(level, "medium")
    if quality.imageQuality < 0.5:
        reasons.append("Image quality is low")
        level = _bump(level, "medium")
    if quality.artifactSuspected:
        reasons.append("Artifact suspected")
        level = _bump(level, "medium")

    return Uncertainty(level=level, reasons=reasons)


def _bump(current: str, candidate: str) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    return current if rank[current] >= rank[candidate] else candidate
