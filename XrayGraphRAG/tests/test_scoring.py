from app.domain.scoring import (
    adaptive_weights,
    aggregate_disease_scores,
    merge_similarity,
)
from app.models.schemas import SimilarCase


def _case(cid: str, sim: float, diseases):
    return SimilarCase(caseId=cid, similarity=sim, diseaseTags=diseases)


def test_higher_similarity_dominates_disease_score():
    cases = [
        _case("a", 0.9, ["pneumonia"]),
        _case("b", 0.2, ["pleural_effusion"]),
    ]
    diseases = aggregate_disease_scores(cases)
    assert diseases[0].disease == "pneumonia"
    assert diseases[0].score > diseases[1].score


def test_non_disease_tags_are_excluded_from_scores():
    cases = [
        _case("a", 0.9, ["support_devices", "no_finding"]),
        _case("b", 0.2, ["pneumonia"]),
    ]
    diseases = aggregate_disease_scores(cases)
    assert [d.disease for d in diseases] == ["pneumonia"]


def test_merge_similarity_uses_weights():
    g = [_case("a", 0.8, ["x"])]
    roi = {
        "right_lung": [_case("a", 1.0, ["x"])],
        "left_lung": [_case("a", 0.5, ["x"])],
        "heart": [_case("a", 0.0, ["x"])],
    }
    weights = {"global": 0.5, "right_lung": 0.2, "left_lung": 0.2, "heart": 0.1}
    merged = merge_similarity(g, roi, weights)
    expected = 0.5 * 0.8 + 0.2 * 1.0 + 0.2 * 0.5 + 0.1 * 0.0
    assert abs(merged[0].similarity - expected) < 1e-6


def test_adaptive_weights_boosts_high_severity():
    base = adaptive_weights({})
    boosted = adaptive_weights({"right_lung": "high"})
    assert boosted["right_lung"] > base["right_lung"]
    assert sum(boosted.values()) <= 1.05  # 합 ~ 1
