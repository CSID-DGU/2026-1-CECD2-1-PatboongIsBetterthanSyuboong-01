"""anomaly model 추론 wrapper. shape 검증 / dtype 보장."""
from __future__ import annotations

import numpy as np

from app.ml.base import AnomalyModel


class ReconstructionService:
    def __init__(self, model: AnomalyModel) -> None:
        self.model = model

    def reconstruct(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 2:
            raise ValueError(f"image must be [H,W], got {image.shape}")
        recon = self.model.reconstruct(image)
        if recon.shape != image.shape:
            raise ValueError(
                f"reconstruction shape mismatch: got {recon.shape} vs {image.shape}"
            )
        return np.clip(recon.astype(np.float32), 0.0, 1.0)
