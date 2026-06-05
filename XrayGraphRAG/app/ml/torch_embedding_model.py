"""(선택) PyTorch 기반 embedding model.

기본 구현은 random-init Conv encoder. 실제 운영에서는 사전학습 backbone(예: timm 모델, MAE,
contrastive 학습된 X-ray encoder)으로 교체한다. 이 모듈은 placeholder 어댑터다.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


class TorchSimpleConvEmbedding:
    def __init__(self, dim: int = 768, image_size: int = 256) -> None:
        import torch
        import torch.nn as nn

        self._torch = torch
        self.dim = dim
        self.image_size = image_size

        self.net = nn.Sequential(
            nn.Conv2d(1, 16, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 32, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(64, dim),
        )
        self.net.eval()

    def embed(self, error_map: np.ndarray) -> np.ndarray:
        torch = self._torch
        with torch.no_grad():
            t = torch.from_numpy(error_map.astype("float32")).unsqueeze(0).unsqueeze(0)
            v = self.net(t).cpu().numpy()[0]
        n = float(np.linalg.norm(v))
        if n < 1e-8:
            return v.astype(np.float32)
        return (v / n).astype(np.float32)


def build_torch_embedding_model(dim: int, image_size: int) -> Optional[TorchSimpleConvEmbedding]:
    try:
        return TorchSimpleConvEmbedding(dim=dim, image_size=image_size)
    except Exception as e:  # pragma: no cover
        print(f"[ml] torch embedding model unavailable, falling back to mock: {e}")
        return None
