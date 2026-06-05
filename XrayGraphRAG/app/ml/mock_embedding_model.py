"""Mock embedding model.

error map을 고정 차원 벡터로 변환한다. 결정론적이며(시드 고정 random projection),
같은 입력은 항상 같은 임베딩을 생성한다. 실제 모델로 교체할 때까지의 placeholder.

방법:
  1) error map을 grid_w x grid_h로 평균 풀링.
  2) flatten 후 fixed random matrix와 곱해 dim 차원으로 투영.
  3) L2 정규화.
"""
from __future__ import annotations

import numpy as np


class MockEmbeddingModel:
    def __init__(self, dim: int = 768, grid: int = 16, seed: int = 1234) -> None:
        self._dim = dim
        self._grid = grid
        rng = np.random.default_rng(seed)
        self._proj = rng.standard_normal((grid * grid, dim)).astype(np.float32) / np.sqrt(grid * grid)

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, error_map: np.ndarray) -> np.ndarray:
        feat = _avg_pool_to_grid(error_map.astype(np.float32), self._grid).reshape(-1)
        v = feat @ self._proj
        n = float(np.linalg.norm(v))
        if n < 1e-8:
            return v.astype(np.float32)
        return (v / n).astype(np.float32)


def _avg_pool_to_grid(x: np.ndarray, g: int) -> np.ndarray:
    h, w = x.shape
    bh = max(1, h // g)
    bw = max(1, w // g)
    Hc = bh * g
    Wc = bw * g
    if Hc != h or Wc != w:
        # 가장자리 잘라 grid에 맞춤(간단함). 실제 모델로 교체 시 의미 없음.
        x = x[:Hc, :Wc]
    out = x.reshape(g, bh, g, bw).mean(axis=(1, 3))
    return out
