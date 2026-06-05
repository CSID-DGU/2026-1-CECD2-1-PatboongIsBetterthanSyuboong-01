"""ROI 통계 -> finding tag 변환 룰."""
from __future__ import annotations

from typing import Dict, List

from app.models.schemas import ROIStats


def derive_finding_tags(roi_stats: Dict[str, ROIStats]) -> List[str]:
    tags: List[str] = []

    def is_high(name: str) -> bool:
        s = roi_stats.get(name)
        return bool(s and s.severity == "high")

    if is_high("right_lung"):
        tags.append("right_lung_high_error")
    if is_high("left_lung"):
        tags.append("left_lung_high_error")
    if is_high("right_lung") and is_high("left_lung"):
        tags.append("bilateral_diffuse_error")
    if is_high("upper_right_lung"):
        tags.append("right_upper_lung_high_error")
    if is_high("lower_right_lung"):
        tags.append("right_lower_lung_high_error")
    if is_high("upper_left_lung"):
        tags.append("left_upper_lung_high_error")
    if is_high("lower_left_lung"):
        tags.append("left_lower_lung_high_error")
    if is_high("pleural_region"):
        tags.append("pleural_region_high_error")
    if is_high("heart"):
        tags.append("cardiac_region_high_error")
    if is_high("mediastinum"):
        tags.append("mediastinum_high_error")

    # 양쪽 폐 mean error가 모두 medium 이상이면 diffuse 패턴
    rr = roi_stats.get("right_lung")
    ll = roi_stats.get("left_lung")
    if rr and ll and rr.severity in ("medium", "high") and ll.severity in ("medium", "high"):
        if "bilateral_diffuse_error" not in tags:
            tags.append("bilateral_diffuse_error")

    return tags
