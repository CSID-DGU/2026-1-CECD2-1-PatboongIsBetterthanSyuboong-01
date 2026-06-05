"""Case 등록 / inference 워크플로우 orchestrator."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import Settings
from app.db.repositories import CaseRepository
from app.domain.findings import derive_finding_tags
from app.domain.scoring import is_supported_disease_tag
from app.models.schemas import (
    CaseRegisterMetadata,
    InferenceResponse,
    NotableFinding,
    PredictedDisease,
    Quality,
    ROIStats,
    SimilarCase,
)
from app.services.agent_service import AgentService
from app.services.embedding_service import EmbeddingService
from app.services.error_map_service import compute_error_map, compute_roi_stats
from app.services.heatmap_service import save_heatmap
from app.services.preprocessing_service import preprocess
from app.services.reasoning_service import ReasoningService
from app.services.reconstruction_service import ReconstructionService
from app.services.roi_mask_service import ROIMaskService
from app.services.similarity_service import SimilarityService
from app.services.storage_service import LocalStorage
from app.utils.id_utils import new_case_key, safe_doc_key
from app.utils.image_utils import save_array_as_png
from app.utils.time_utils import utc_now_iso


class CaseService:
    def __init__(
        self,
        settings: Settings,
        repo: CaseRepository,
        recon: ReconstructionService,
        roi: ROIMaskService,
        embedder: EmbeddingService,
        similarity: SimilarityService,
        reasoning: ReasoningService,
        agent: AgentService,
        storage_images: LocalStorage,
        storage_recon: LocalStorage,
        storage_heatmap: LocalStorage,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.recon = recon
        self.roi = roi
        self.embedder = embedder
        self.similarity = similarity
        self.reasoning = reasoning
        self.agent = agent
        self.s_images = storage_images
        self.s_recon = storage_recon
        self.s_heatmap = storage_heatmap

    # ---------- 등록 ----------
    def register_case(
        self,
        image_bytes: bytes,
        original_filename: str,
        disease_tags: List[str],
        finding_tags: Optional[List[str]],
        metadata: CaseRegisterMetadata,
    ) -> Dict[str, Any]:
        case_key = new_case_key()
        ext = Path(original_filename or ".png").suffix.lower() or ".png"

        # 1) 원본 저장
        img_path = self.s_images.resolve(f"{case_key}{ext}")
        img_path.write_bytes(image_bytes)

        # 2) workflow
        image = preprocess(image_bytes, self.settings.IMAGE_SIZE)
        recon = self.recon.reconstruct(image)
        recon_path = self.s_recon.resolve(f"{case_key}_recon.png")
        save_array_as_png(recon, recon_path)

        error_map = compute_error_map(image, recon)
        masks = self.roi.generate(image)
        roi_stats = compute_roi_stats(error_map, masks, self.settings)

        embeddings = self.embedder.embed_all(error_map, masks)

        # 3) heatmap 저장
        heatmap_path = self.s_heatmap.resolve(f"{case_key}_heatmap.png")
        save_heatmap(error_map, heatmap_path, original=image, alpha=0.55)

        # 4) finding tag 자동 도출 + 입력 finding 병합
        disease_tags = [d for d in disease_tags if is_supported_disease_tag(d)]
        auto_findings = derive_finding_tags(roi_stats)
        merged_findings = list(dict.fromkeys((finding_tags or []) + auto_findings))

        # 5) ArangoDB document 작성
        doc = {
            "_key": case_key,
            "imagePath": str(img_path),
            "reconPath": str(recon_path),
            "heatmapPath": str(heatmap_path),
            "view": metadata.view or "PA",
            "modelVersion": metadata.modelVersion or self.settings.MODEL_VERSION,
            "maskVersion": metadata.maskVersion or self.settings.MASK_VERSION,
            "embeddingVersion": self.settings.EMBEDDING_VERSION,
            "globalErrorEmbedding": embeddings["global"].tolist(),
            "leftLungErrorEmbedding": embeddings["left_lung"].tolist(),
            "rightLungErrorEmbedding": embeddings["right_lung"].tolist(),
            "heartErrorEmbedding": embeddings["heart"].tolist(),
            "roiStats": {k: _stats_to_dict(v) for k, v in roi_stats.items()},
            "diseaseTags": disease_tags,
            "findingTags": merged_findings,
            "quality": Quality().model_dump(),
            "createdAt": utc_now_iso(),
        }
        # 환자/메타 부가 필드(있으면 함께 저장)
        for k in ("patientAge", "sex", "source"):
            v = getattr(metadata, k, None)
            if v is not None:
                doc[k] = v

        self.repo.insert_case(doc)
        # edges
        for d in disease_tags:
            self.repo.add_case_disease(case_key, safe_doc_key(d))
        for f in merged_findings:
            self.repo.add_case_finding(case_key, safe_doc_key(f))
        for roi_name, stats in roi_stats.items():
            if stats.severity in ("medium", "high"):
                self.repo.add_case_roi_anomaly(
                    case_key,
                    roi_name,
                    mean_error=stats.meanError,
                    p95_error=stats.p95Error,
                    severity=stats.severity,
                )
        return {"caseId": case_key, "status": "created"}

    # ---------- inference ----------
    def infer(
        self,
        image_bytes: bytes,
        view: Optional[str],
        model_version: Optional[str],
        mask_version: Optional[str],
        top_k: int,
    ) -> InferenceResponse:
        image = preprocess(image_bytes, self.settings.IMAGE_SIZE)
        recon = self.recon.reconstruct(image)
        error_map = compute_error_map(image, recon)
        masks = self.roi.generate(image)
        roi_stats = compute_roi_stats(error_map, masks, self.settings)
        embeddings = self.embedder.embed_all(error_map, masks)

        # 임시 heatmap(저장 후 path 반환). 영구 저장은 register와 분리.
        tmp_key = new_case_key()
        heatmap_path = self.s_heatmap.resolve(f"query_{tmp_key}_heatmap.png")
        save_heatmap(error_map, heatmap_path, original=image, alpha=0.55)
        heatmap_url = self._storage_url(heatmap_path)

        # ROI severity dict
        roi_severity = {k: v.severity for k, v in roi_stats.items()}
        similar_cases = self.similarity.search_combined(
            embeddings,
            view=view,
            model_version=model_version or self.settings.MODEL_VERSION,
            mask_version=mask_version or self.settings.MASK_VERSION,
            top_k=top_k,
            roi_severity=roi_severity,
        )

        # query case 자동 finding (참고용)
        query_findings = derive_finding_tags(roi_stats)

        reasoning_out = self.reasoning.reason(
            similar_cases=similar_cases,
            current_roi_stats=roi_stats,
            quality=Quality(),
            view=view,
            model_version=model_version,
        )

        explanation = self.agent.explain(
            diseases=reasoning_out["predictedDiseases"],
            notable_findings=reasoning_out["notableFindings"],
            similar_cases=similar_cases,
            roi_stats=roi_stats,
            uncertainty=reasoning_out["uncertainty"],
            graph_evidence=reasoning_out["graphEvidence"],
        )

        return InferenceResponse(
            queryCase={
                "heatmapPath": heatmap_url,
                "roiStats": {k: _stats_to_dict(v) for k, v in roi_stats.items()},
                "autoFindings": query_findings,
                "view": view or "PA",
                "modelVersion": model_version or self.settings.MODEL_VERSION,
                "maskVersion": mask_version or self.settings.MASK_VERSION,
            },
            predictedDiseases=reasoning_out["predictedDiseases"],
            notableFindings=reasoning_out["notableFindings"],
            similarCases=similar_cases,
            uncertainty=reasoning_out["uncertainty"],
            explanation=explanation,
            heatmapPath=heatmap_url,
            warning=self.settings.SAFETY_NOTICE,
        )

    def _storage_url(self, path: Path) -> str:
        rel = path.resolve().relative_to(self.settings.STORAGE_DIR.resolve())
        return "/storage/" + rel.as_posix()


def _stats_to_dict(s: ROIStats) -> Dict[str, Any]:
    return s.model_dump()
