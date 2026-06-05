"""error map 계산 + ROI 통계 계산."""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from app.config import Settings
from app.models.schemas import ROIStats


def compute_error_map(image: np.ndarray, recon: np.ndarray) -> np.ndarray:
    """|input - recon|, 0~1 정규화."""
    if image.shape != recon.shape:
        raise ValueError(f"shape mismatch: {image.shape} vs {recon.shape}")
    err = np.abs(image.astype(np.float32) - recon.astype(np.float32))
    mx = float(err.max())
    if mx > 0:
        err = err / mx
    return err.astype(np.float32)


def apply_roi_mask(error_map: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if error_map.shape != mask.shape:
        raise ValueError(f"shape mismatch: {error_map.shape} vs {mask.shape}")
    m = (mask > 0.5).astype(np.float32)
    return error_map * m


def severity_from(p95: float, high_area_ratio: float, settings: Settings) -> str:
    if p95 >= settings.SEVERITY_HIGH_P95 or high_area_ratio >= settings.SEVERITY_HIGH_AREA:
        return "high"
    if p95 >= settings.SEVERITY_MEDIUM_P95:
        return "medium"
    return "low"


def compute_roi_stats(
    error_map: np.ndarray,
    masks: Dict[str, np.ndarray],
    settings: Settings,
    high_threshold: float = 0.30,
) -> Dict[str, ROIStats]:
    """ROI별 mean/max/p95/area/connected component 통계."""
    out: Dict[str, ROIStats] = {}
    total_pixels = float(error_map.size)
    for name, m in masks.items():
        m_bin = (m > 0.5)
        roi_err = error_map[m_bin]
        area = float(m_bin.sum())
        if area == 0 or roi_err.size == 0:
            stats = ROIStats(
                meanError=0.0, maxError=0.0, p95Error=0.0, stdError=0.0,
                areaRatio=0.0, highErrorAreaRatio=0.0,
                connectedComponentCount=0, largestComponentArea=0,
                severity="low",
            )
            out[name] = stats
            continue
        mean_e = float(roi_err.mean())
        max_e = float(roi_err.max())
        p95 = float(np.percentile(roi_err, 95))
        std_e = float(roi_err.std())
        area_ratio = area / total_pixels

        high = error_map * m_bin.astype(np.float32) >= high_threshold
        n_high = int(high.sum())
        high_area_ratio = float(n_high) / max(1.0, area)

        cc_count, largest = _connected_components_count(high)

        stats = ROIStats(
            meanError=mean_e,
            maxError=max_e,
            p95Error=p95,
            stdError=std_e,
            areaRatio=area_ratio,
            highErrorAreaRatio=high_area_ratio,
            connectedComponentCount=cc_count,
            largestComponentArea=largest,
            severity=severity_from(p95, high_area_ratio, settings),
        )
        out[name] = stats
    return out


def _connected_components_count(binary: np.ndarray) -> Tuple[int, int]:
    """OpenCV 의존성 없이 4-connectivity flood fill."""
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    count = 0
    largest = 0
    for y in range(h):
        for x in range(w):
            if binary[y, x] and not visited[y, x]:
                # iterative BFS
                stack = [(y, x)]
                visited[y, x] = True
                area = 0
                while stack:
                    cy, cx = stack.pop()
                    area += 1
                    if cy > 0 and binary[cy - 1, cx] and not visited[cy - 1, cx]:
                        visited[cy - 1, cx] = True
                        stack.append((cy - 1, cx))
                    if cy < h - 1 and binary[cy + 1, cx] and not visited[cy + 1, cx]:
                        visited[cy + 1, cx] = True
                        stack.append((cy + 1, cx))
                    if cx > 0 and binary[cy, cx - 1] and not visited[cy, cx - 1]:
                        visited[cy, cx - 1] = True
                        stack.append((cy, cx - 1))
                    if cx < w - 1 and binary[cy, cx + 1] and not visited[cy, cx + 1]:
                        visited[cy, cx + 1] = True
                        stack.append((cy, cx + 1))
                count += 1
                if area > largest:
                    largest = area
    return count, largest
