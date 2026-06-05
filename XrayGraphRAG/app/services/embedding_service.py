"""ROI별 error embedding 생성."""
from __future__ import annotations

from typing import Dict

import numpy as np

from app.ml.base import EmbeddingModel
from app.services.error_map_service import apply_roi_mask


class EmbeddingService:
    def __init__(self, model: EmbeddingModel) -> None:
        self.model = model

    @property
    def dim(self) -> int:
        return self.model.dim

    def embed_global(self, error_map: np.ndarray) -> np.ndarray:
        return self.model.embed(error_map)

    def embed_roi(self, error_map: np.ndarray, mask: np.ndarray) -> np.ndarray:
        masked = apply_roi_mask(error_map, mask)
        return self.model.embed(masked)

    def embed_all(self, error_map: np.ndarray, masks: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        out: Dict[str, np.ndarray] = {"global": self.embed_global(error_map)}
        for key in ("left_lung", "right_lung", "heart"):
            if key in masks:
                out[key] = self.embed_roi(error_map, masks[key])
            else:
                out[key] = np.zeros(self.dim, dtype=np.float32)
        return out
