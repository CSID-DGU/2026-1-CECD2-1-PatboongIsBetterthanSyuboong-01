"""ROI mask 생성 service. ML 인터페이스를 호출하고 dict 형식을 표준화."""
from __future__ import annotations

from typing import Dict

import numpy as np

from app.ml.base import ROIMaskModel


class ROIMaskService:
    def __init__(self, model: ROIMaskModel) -> None:
        self.model = model

    def generate(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        masks = self.model.generate_masks(image)
        # 모든 마스크를 [H,W] uint8 0/1로 통일
        out: Dict[str, np.ndarray] = {}
        for k, v in masks.items():
            arr = np.asarray(v)
            if arr.ndim == 3:
                arr = arr[0]
            out[k] = (arr > 0.5).astype(np.uint8)
        return out
