"""mock 모델 + fake ArangoDB로 케이스 등록 + inference 흐름 통합 테스트."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.config import get_settings
from app.ml.factory import build_models
from app.services.agent_service import AgentService
from app.services.case_service import CaseService
from app.services.embedding_service import EmbeddingService
from app.services.reasoning_service import ReasoningService
from app.services.reconstruction_service import ReconstructionService
from app.services.roi_mask_service import ROIMaskService
from app.services.similarity_service import SimilarityService
from app.services.storage_service import LocalStorage

from tests.fakes import _FakeRepo


def _make_fake_xray_bytes(seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(256, 256), dtype=np.uint8)
    # 중심부에 밝은 패치(병변 흉내)
    arr[100:140, 130:170] = 240
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_service():
    s = get_settings()
    repo = _FakeRepo()
    anomaly, roi, embedder = build_models(s)
    return CaseService(
        settings=s,
        repo=repo,
        recon=ReconstructionService(anomaly),
        roi=ROIMaskService(roi),
        embedder=EmbeddingService(embedder),
        similarity=SimilarityService(repo),
        reasoning=ReasoningService(repo, s),
        agent=AgentService(s),
        storage_images=LocalStorage(s.images_dir),
        storage_recon=LocalStorage(s.recon_dir),
        storage_heatmap=LocalStorage(s.heatmap_dir),
    ), repo


def test_register_then_infer_returns_predicted_disease():
    svc, repo = _build_service()

    # 3개 case 등록(같은 disease)
    for i in range(3):
        svc.register_case(
            image_bytes=_make_fake_xray_bytes(seed=i),
            original_filename=f"a{i}.png",
            disease_tags=["pneumonia"],
            finding_tags=None,
            metadata=__import__("app.models.schemas", fromlist=["CaseRegisterMetadata"]).CaseRegisterMetadata(),
        )

    # 비슷한 패치를 가진 새 이미지로 inference
    res = svc.infer(
        image_bytes=_make_fake_xray_bytes(seed=42),
        view=None,
        model_version=None,
        mask_version=None,
        top_k=3,
    )

    assert "queryCase" in res.model_dump()
    assert res.predictedDiseases, "predictedDiseases should not be empty"
    # mock embedding이 결정론적이라 등록한 disease가 후보에 떠야 함
    assert any(d.disease == "pneumonia" for d in res.predictedDiseases)
    assert res.warning  # safety notice
    assert res.uncertainty.level in ("low", "medium", "high")
