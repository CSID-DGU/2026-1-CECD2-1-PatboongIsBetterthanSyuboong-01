"""ML 인터페이스 정의. 실제 구현/모의 구현이 모두 같은 시그니처를 따른다."""
from __future__ import annotations

from typing import Dict, Protocol

import numpy as np


class AnomalyModel(Protocol):
    """입력 X-ray (1장, [H, W] 0~1)에 대해 reconstruction을 반환."""

    def reconstruct(self, image: np.ndarray) -> np.ndarray:  # pragma: no cover - 인터페이스
        ...


class ROIMaskModel(Protocol):
    """입력 X-ray (1장, [H, W] 0~1)에 대해 ROI mask dict 반환.

    반환 dict의 key는 다음 중 일부를 포함해야 한다:
      left_lung, right_lung, heart, full_lung,
      upper_left_lung, lower_left_lung, upper_right_lung, lower_right_lung,
      pleural_region, mediastinum
    각 마스크는 [H, W] uint8 또는 float32(0/1).
    """

    def generate_masks(self, image: np.ndarray) -> Dict[str, np.ndarray]:  # pragma: no cover
        ...


class EmbeddingModel(Protocol):
    """error map에서 고정 차원 임베딩 추출."""

    @property
    def dim(self) -> int:  # pragma: no cover
        ...

    def embed(self, error_map: np.ndarray) -> np.ndarray:  # pragma: no cover
        ...
