"""Mock ROI model.

실제 segmentation 모델이 없는 환경에서 사용. 단순 위치 휴리스틱으로 폐/심장/세부 ROI
이진 마스크를 만든다. 폐는 영상의 가운데 세로 띠 양쪽, 심장은 중앙. 좌우 폐는 좌/우 절반,
상하 폐는 위/아래 절반으로 추가 ROI까지 생성한다.

이 마스크는 의학적으로 정확하지 않다 - mock-first 시연/테스트용.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


class MockROIModel:
    def generate_masks(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        if image.ndim != 2:
            raise ValueError(f"image must be [H,W], got {image.shape}")
        h, w = image.shape

        full_lung = _ellipse_mask(h, w, cy=int(h * 0.55), cx=w // 2, ry=int(h * 0.42), rx=int(w * 0.42))
        heart = _ellipse_mask(h, w, cy=int(h * 0.62), cx=int(w * 0.45), ry=int(h * 0.16), rx=int(w * 0.13))
        full_lung = np.maximum(full_lung - heart, 0).astype(np.uint8)

        left = full_lung.copy()
        right = full_lung.copy()
        right[:, : w // 2] = 0
        left[:, w // 2 :] = 0

        upper_left = left.copy()
        lower_left = left.copy()
        upper_left[h // 2 :, :] = 0
        lower_left[: h // 2, :] = 0
        upper_right = right.copy()
        lower_right = right.copy()
        upper_right[h // 2 :, :] = 0
        lower_right[: h // 2, :] = 0

        # pleural_region: 폐 외곽 1픽셀 ring(간단 구현: erode 차이)
        pleural = _border_band(full_lung, width=max(2, h // 64))

        # mediastinum: 양 폐 사이 가운데 좁은 띠
        mediastinum = np.zeros_like(full_lung)
        ml = int(w * 0.45)
        mr = int(w * 0.55)
        mt = int(h * 0.30)
        mb = int(h * 0.85)
        mediastinum[mt:mb, ml:mr] = 1

        return {
            "full_lung": full_lung,
            "left_lung": left.astype(np.uint8),
            "right_lung": right.astype(np.uint8),
            "heart": heart.astype(np.uint8),
            "upper_left_lung": upper_left.astype(np.uint8),
            "lower_left_lung": lower_left.astype(np.uint8),
            "upper_right_lung": upper_right.astype(np.uint8),
            "lower_right_lung": lower_right.astype(np.uint8),
            "pleural_region": pleural.astype(np.uint8),
            "mediastinum": mediastinum.astype(np.uint8),
        }


def _ellipse_mask(h: int, w: int, cy: int, cx: int, ry: int, rx: int) -> np.ndarray:
    yy, xx = np.ogrid[:h, :w]
    e = ((yy - cy) / float(ry)) ** 2 + ((xx - cx) / float(rx)) ** 2
    return (e <= 1.0).astype(np.uint8)


def _border_band(mask: np.ndarray, width: int = 3) -> np.ndarray:
    h, w = mask.shape
    eroded = mask.copy()
    for _ in range(width):
        e = np.zeros_like(eroded)
        e[1:-1, 1:-1] = (
            eroded[1:-1, 1:-1] & eroded[:-2, 1:-1] & eroded[2:, 1:-1]
            & eroded[1:-1, :-2] & eroded[1:-1, 2:]
        )
        eroded = e
    return (mask & ~eroded.astype(bool)).astype(np.uint8)
