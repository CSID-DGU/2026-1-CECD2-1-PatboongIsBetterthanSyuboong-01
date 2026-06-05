"""ML factory. 환경변수 토글에 따라 mock 또는 torch adapter를 만든다."""
from __future__ import annotations

from typing import Tuple

from app.config import Settings
from app.ml.base import AnomalyModel, EmbeddingModel, ROIMaskModel
from app.ml.mock_anomaly_model import MockAnomalyModel
from app.ml.mock_embedding_model import MockEmbeddingModel
from app.ml.mock_roi_model import MockROIModel


def build_models(settings: Settings) -> Tuple[AnomalyModel, ROIMaskModel, EmbeddingModel]:
    anomaly: AnomalyModel = MockAnomalyModel()
    if settings.USE_TORCH_ANOMALY:
        from app.ml.torch_anomaly_model import build_torch_anomaly_model

        m = build_torch_anomaly_model(settings.SQUID_MODEL_DIR)
        if m is not None:
            anomaly = m

    roi: ROIMaskModel = MockROIModel()
    # 실제 ROI(HybridGNet 등)는 향후 어댑터 추가 위치.

    embedder: EmbeddingModel = MockEmbeddingModel(dim=settings.EMBEDDING_DIM)
    if settings.USE_TORCH_EMBEDDING:
        from app.ml.torch_embedding_model import build_torch_embedding_model

        e = build_torch_embedding_model(dim=settings.EMBEDDING_DIM, image_size=settings.IMAGE_SIZE)
        if e is not None:
            embedder = e

    return anomaly, roi, embedder
