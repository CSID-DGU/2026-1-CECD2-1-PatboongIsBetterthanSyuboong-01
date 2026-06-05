"""Similarity 검색 service. global + ROI 검색을 합쳐 최종 점수 산출."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from app.db.repositories import CaseRepository
from app.domain.scoring import adaptive_weights, merge_similarity
from app.models.schemas import SimilarCase


_FIELD_MAP = {
    "global": "globalErrorEmbedding",
    "left_lung": "leftLungErrorEmbedding",
    "right_lung": "rightLungErrorEmbedding",
    "heart": "heartErrorEmbedding",
}


class SimilarityService:
    def __init__(self, repo: CaseRepository) -> None:
        self.repo = repo

    def search_global(
        self,
        embedding: np.ndarray,
        *,
        view: Optional[str] = None,
        model_version: Optional[str] = None,
        mask_version: Optional[str] = None,
        top_k: int = 20,
    ) -> List[SimilarCase]:
        return self.repo.vector_search(
            _FIELD_MAP["global"],
            embedding.tolist(),
            view=view,
            model_version=model_version,
            mask_version=mask_version,
            top_k=top_k,
        )

    def search_combined(
        self,
        embeddings: Dict[str, np.ndarray],
        *,
        view: Optional[str] = None,
        model_version: Optional[str] = None,
        mask_version: Optional[str] = None,
        top_k: int = 20,
        roi_severity: Optional[Dict[str, str]] = None,
    ) -> List[SimilarCase]:
        global_results = self.search_global(
            embeddings["global"],
            view=view,
            model_version=model_version,
            mask_version=mask_version,
            top_k=top_k,
        )
        roi_results: Dict[str, List[SimilarCase]] = {}
        for roi_name, field in _FIELD_MAP.items():
            if roi_name == "global":
                continue
            emb = embeddings.get(roi_name)
            if emb is None:
                continue
            roi_results[roi_name] = self.repo.vector_search(
                field,
                np.asarray(emb).tolist(),
                view=view,
                model_version=model_version,
                mask_version=mask_version,
                top_k=top_k,
            )
        weights = adaptive_weights(roi_severity or {})
        merged = merge_similarity(global_results, roi_results, weights)
        return merged[:top_k]
