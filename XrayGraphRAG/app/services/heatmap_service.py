"""heatmap 생성/저장. matplotlib는 선택 의존이며, 없으면 numpy/PIL로 fallback."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.utils.image_utils import normalize_minmax


_JET_RGB = None  # lazy


def _jet_lookup() -> np.ndarray:
    """matplotlib 없이 jet에 가까운 RGB lookup table(256x3 uint8)."""
    global _JET_RGB
    if _JET_RGB is not None:
        return _JET_RGB
    x = np.linspace(0, 1, 256, dtype=np.float32)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    rgb = np.stack([r, g, b], axis=-1)
    _JET_RGB = (rgb * 255.0).astype(np.uint8)
    return _JET_RGB


def save_heatmap(error_map: np.ndarray, dst: Path, *, original: np.ndarray | None = None, alpha: float = 0.5) -> Path:
    """heatmap 또는 overlay 저장. dst는 .png로 강제."""
    dst = dst.with_suffix(".png")
    dst.parent.mkdir(parents=True, exist_ok=True)
    norm = normalize_minmax(error_map)
    idx = (np.clip(norm, 0, 1) * 255).astype(np.uint8)
    cmap = _jet_lookup()
    rgb = cmap[idx]  # [H,W,3]
    if original is not None:
        gray = np.clip(original, 0.0, 1.0)
        gray3 = np.repeat((gray * 255.0).astype(np.uint8)[..., None], 3, axis=-1)
        out = (gray3.astype(np.float32) * (1 - alpha) + rgb.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)
    else:
        out = rgb
    Image.fromarray(out).save(str(dst))
    return dst
