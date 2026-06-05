"""Mock anomaly model.

실제 SQUID/AE 모델이 없을 때도 end-to-end가 동작하도록, 입력에 살짝 blur를 적용한 것을
"reconstruction"으로 취급한다. 이 경우 error map = |원본 - blur| 가 되어 고주파 영역(병변/엣지)이
강조되는 의미 있는 분포가 된다. 결정론적이라 테스트에 유리하다.
"""
from __future__ import annotations

import numpy as np


class MockAnomalyModel:
    def __init__(self, blur_kernel: int = 9) -> None:
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        self.k = blur_kernel

    def reconstruct(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 2:
            raise ValueError(f"image must be [H,W], got {image.shape}")
        return _box_blur(image.astype(np.float32), self.k)


def _box_blur(img: np.ndarray, k: int) -> np.ndarray:
    """OpenCV 의존성 없이 동작하는 box blur. integral image 기반 O(HW)."""
    h, w = img.shape
    pad = k // 2
    padded = np.pad(img, ((pad + 1, pad), (pad + 1, pad)), mode="edge")
    ii = padded.cumsum(axis=0).cumsum(axis=1).astype(np.float64)
    a = ii[k:, k:]
    b = ii[:-k, k:]
    c = ii[k:, :-k]
    d = ii[:-k, :-k]
    s = a - b - c + d
    out = (s / float(k * k)).astype(np.float32)
    return out[:h, :w]
