import numpy as np

from app.config import get_settings
from app.services.error_map_service import compute_roi_stats


def test_roi_stats_basic():
    s = get_settings()
    err = np.zeros((10, 10), dtype=np.float32)
    err[0:2, 0:2] = 0.9  # 4 high pixels in mask region
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0:5, 0:5] = 1
    masks = {"left_lung": mask}
    out = compute_roi_stats(err, masks, s, high_threshold=0.5)
    stats = out["left_lung"]
    assert stats.areaRatio == 25 / 100
    assert stats.maxError >= 0.9 - 1e-6
    assert stats.connectedComponentCount == 1
    assert stats.severity in ("medium", "high")


def test_roi_stats_empty_mask():
    s = get_settings()
    err = np.full((4, 4), 0.4, dtype=np.float32)
    mask = np.zeros((4, 4), dtype=np.uint8)
    out = compute_roi_stats(err, {"r": mask}, s)
    assert out["r"].areaRatio == 0.0
    assert out["r"].severity == "low"
