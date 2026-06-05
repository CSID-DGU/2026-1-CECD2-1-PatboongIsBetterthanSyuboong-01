from app.config import get_settings
from app.domain.uncertainty import assess_uncertainty
from app.models.schemas import PredictedDisease, Quality, SimilarCase


def test_high_uncertainty_when_top1_low():
    s = get_settings()
    cases = [SimilarCase(caseId="a", similarity=0.30, diseaseTags=["x"])]
    diseases = [PredictedDisease(disease="x", score=1.0, supportCases=1, reason="r")]
    u = assess_uncertainty(cases, diseases, Quality(), s)
    assert u.level == "high"


def test_medium_uncertainty_when_top12_close():
    s = get_settings()
    cases = [SimilarCase(caseId=str(i), similarity=0.9, diseaseTags=["x", "y"]) for i in range(10)]
    diseases = [
        PredictedDisease(disease="x", score=0.55, supportCases=10, reason="r"),
        PredictedDisease(disease="y", score=0.50, supportCases=10, reason="r"),
    ]
    u = assess_uncertainty(cases, diseases, Quality(), s)
    assert u.level in ("medium", "high")


def test_no_cases_is_high():
    s = get_settings()
    u = assess_uncertainty([], [], Quality(), s)
    assert u.level == "high"
