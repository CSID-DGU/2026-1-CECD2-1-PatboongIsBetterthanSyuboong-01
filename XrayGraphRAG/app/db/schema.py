"""Collection / Graph / Vector index 초기화."""
from __future__ import annotations

import logging
from typing import Iterable

from arango.database import StandardDatabase

from app.config import Settings

logger = logging.getLogger(__name__)


DOCUMENT_COLLECTIONS = (
    "xray_cases",
    "diseases",
    "findings",
    "rois",
    "model_versions",
)

EDGE_COLLECTIONS = (
    "case_has_disease",
    "case_has_finding",
    "case_has_roi_anomaly",
    "disease_related_finding",
    "finding_located_in_roi",
)


VECTOR_FIELDS = (
    "globalErrorEmbedding",
    "leftLungErrorEmbedding",
    "rightLungErrorEmbedding",
    "heartErrorEmbedding",
)

DEFAULT_DISEASES = (
    # CheXpert 라벨 중 실제 상병으로 다루는 항목만 disease 노드로 시드한다.
    # no_finding은 정상 표현, support_devices는 기기/삽관 태그라 상병 추론 대상에서 제외한다.
    {"_key": "enlarged_cardiomediastinum", "name": "enlarged_cardiomediastinum",
     "displayName": "Enlarged Cardiomediastinum",
     "description": "Widened cardiomediastinal silhouette"},
    {"_key": "cardiomegaly", "name": "cardiomegaly", "displayName": "Cardiomegaly",
     "description": "Enlarged cardiac silhouette"},
    {"_key": "lung_opacity", "name": "lung_opacity", "displayName": "Lung Opacity",
     "description": "Generic radiographic opacity in lung field"},
    {"_key": "lung_lesion", "name": "lung_lesion", "displayName": "Lung Lesion",
     "description": "Focal lung lesion (mass/nodule)"},
    {"_key": "edema", "name": "edema", "displayName": "Pulmonary Edema",
     "description": "Fluid in alveoli/interstitium"},
    {"_key": "consolidation", "name": "consolidation", "displayName": "Consolidation",
     "description": "Alveolar filling pattern"},
    {"_key": "pneumonia", "name": "pneumonia", "displayName": "Pneumonia",
     "description": "Inflammatory lung opacity pattern"},
    {"_key": "atelectasis", "name": "atelectasis", "displayName": "Atelectasis",
     "description": "Lung collapse / loss of volume"},
    {"_key": "pneumothorax", "name": "pneumothorax", "displayName": "Pneumothorax",
     "description": "Air in pleural space"},
    {"_key": "pleural_effusion", "name": "pleural_effusion", "displayName": "Pleural Effusion",
     "description": "Fluid in pleural space"},
    {"_key": "pleural_other", "name": "pleural_other", "displayName": "Pleural Other",
     "description": "Other pleural abnormalities"},
    {"_key": "fracture", "name": "fracture", "displayName": "Fracture",
     "description": "Bone fracture"},
)

DEFAULT_ROIS = (
    {"_key": "left_lung", "name": "left_lung", "displayName": "Left Lung"},
    {"_key": "right_lung", "name": "right_lung", "displayName": "Right Lung"},
    {"_key": "heart", "name": "heart", "displayName": "Heart"},
    {"_key": "full_lung", "name": "full_lung", "displayName": "Full Lung"},
    {"_key": "upper_left_lung", "name": "upper_left_lung", "displayName": "Upper Left Lung"},
    {"_key": "lower_left_lung", "name": "lower_left_lung", "displayName": "Lower Left Lung"},
    {"_key": "upper_right_lung", "name": "upper_right_lung", "displayName": "Upper Right Lung"},
    {"_key": "lower_right_lung", "name": "lower_right_lung", "displayName": "Lower Right Lung"},
    {"_key": "pleural_region", "name": "pleural_region", "displayName": "Pleural Region"},
    {"_key": "mediastinum", "name": "mediastinum", "displayName": "Mediastinum"},
)

DEFAULT_FINDINGS = (
    {"_key": "right_lower_lung_high_error",
     "description": "High reconstruction error concentrated in right lower lung region"},
    {"_key": "right_upper_lung_high_error",
     "description": "High reconstruction error concentrated in right upper lung region"},
    {"_key": "left_lower_lung_high_error",
     "description": "High reconstruction error concentrated in left lower lung region"},
    {"_key": "left_upper_lung_high_error",
     "description": "High reconstruction error concentrated in left upper lung region"},
    {"_key": "right_lung_high_error", "description": "Right lung diffuse high error"},
    {"_key": "left_lung_high_error", "description": "Left lung diffuse high error"},
    {"_key": "bilateral_diffuse_error", "description": "Both lungs show high reconstruction error"},
    {"_key": "pleural_region_high_error", "description": "High error along pleural region"},
    {"_key": "cardiac_region_high_error", "description": "High error in cardiac region"},
    {"_key": "mediastinum_high_error", "description": "High error in mediastinum"},
)

# disease ↔ finding 도메인 지식(휴리스틱). 실제 운영에서는 전문가 룰/문헌으로 채운다.
DEFAULT_DISEASE_FINDING_EDGES = (
    ("pneumonia", "right_lower_lung_high_error", 0.8),
    ("pneumonia", "right_upper_lung_high_error", 0.6),
    ("pneumonia", "left_lower_lung_high_error", 0.7),
    ("pneumonia", "consolidation", 0.7),
    ("pleural_effusion", "pleural_region_high_error", 0.8),
    ("pleural_effusion", "right_lower_lung_high_error", 0.5),
    ("cardiomegaly", "cardiac_region_high_error", 0.9),
    ("atelectasis", "left_lower_lung_high_error", 0.6),
    ("edema", "bilateral_diffuse_error", 0.7),
)

DEFAULT_FINDING_ROI_EDGES = (
    ("right_lower_lung_high_error", "lower_right_lung"),
    ("right_upper_lung_high_error", "upper_right_lung"),
    ("left_lower_lung_high_error", "lower_left_lung"),
    ("left_upper_lung_high_error", "upper_left_lung"),
    ("right_lung_high_error", "right_lung"),
    ("left_lung_high_error", "left_lung"),
    ("pleural_region_high_error", "pleural_region"),
    ("cardiac_region_high_error", "heart"),
    ("mediastinum_high_error", "mediastinum"),
    ("bilateral_diffuse_error", "full_lung"),
)


def ensure_collections(db: StandardDatabase) -> None:
    for name in DOCUMENT_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name)
    for name in EDGE_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name, edge=True)


def ensure_graph(db: StandardDatabase, settings: Settings) -> None:
    name = settings.ARANGO_GRAPH_NAME
    edge_defs = [
        {"edge_collection": "case_has_disease",
         "from_vertex_collections": ["xray_cases"],
         "to_vertex_collections": ["diseases"]},
        {"edge_collection": "case_has_finding",
         "from_vertex_collections": ["xray_cases"],
         "to_vertex_collections": ["findings"]},
        {"edge_collection": "case_has_roi_anomaly",
         "from_vertex_collections": ["xray_cases"],
         "to_vertex_collections": ["rois"]},
        {"edge_collection": "disease_related_finding",
         "from_vertex_collections": ["diseases"],
         "to_vertex_collections": ["findings"]},
        {"edge_collection": "finding_located_in_roi",
         "from_vertex_collections": ["findings"],
         "to_vertex_collections": ["rois"]},
    ]

    if db.has_graph(name):
        return
    db.create_graph(name, edge_definitions=edge_defs)


def ensure_vector_indexes(db: StandardDatabase, settings: Settings) -> dict:
    """ArangoDB 3.12+ vector index 생성. 미지원 빌드면 fallback 모드(없이)로 동작.

    반환 dict: {"vector_supported": bool, "details": [...]}
    """
    coll = db.collection("xray_cases")
    details = []
    supported = True
    for field in VECTOR_FIELDS:
        index_name = f"{field}_cosine"
        try:
            existing = [i for i in coll.indexes() if i.get("name") == index_name]
            if existing:
                details.append({"field": field, "status": "exists"})
                continue
            coll.add_index({
                "name": index_name,
                "type": "vector",
                "fields": [field],
                "params": {
                    "metric": settings.VECTOR_METRIC,
                    "dimension": settings.EMBEDDING_DIM,
                    "nLists": settings.VECTOR_NLISTS,
                    "defaultNProbe": settings.VECTOR_NPROBE,
                    "trainingIterations": settings.VECTOR_TRAINING_ITERS,
                },
                "storedValues": ["view", "modelVersion", "maskVersion"],
            })
            details.append({"field": field, "status": "created"})
        except Exception as e:  # pragma: no cover - 환경 의존
            supported = False
            details.append({"field": field, "status": "unsupported", "error": str(e)})
    return {"vector_supported": supported, "details": details}


def seed_defaults(db: StandardDatabase) -> None:
    _upsert_many(db, "diseases", DEFAULT_DISEASES)
    _upsert_many(db, "rois", DEFAULT_ROIS)
    _upsert_many(db, "findings", DEFAULT_FINDINGS)

    drf = db.collection("disease_related_finding")
    for d, f, w in DEFAULT_DISEASE_FINDING_EDGES:
        edge_key = f"{d}__{f}"
        doc = {
            "_key": edge_key,
            "_from": f"diseases/{d}",
            "_to": f"findings/{f}",
            "weight": w,
        }
        if not drf.has(edge_key):
            try:
                drf.insert(doc)
            except Exception:
                drf.update(doc)

    flr = db.collection("finding_located_in_roi")
    for f, r in DEFAULT_FINDING_ROI_EDGES:
        edge_key = f"{f}__{r}"
        doc = {
            "_key": edge_key,
            "_from": f"findings/{f}",
            "_to": f"rois/{r}",
        }
        if not flr.has(edge_key):
            try:
                flr.insert(doc)
            except Exception:
                flr.update(doc)


def _upsert_many(db: StandardDatabase, coll_name: str, docs: Iterable[dict]) -> None:
    coll = db.collection(coll_name)
    for d in docs:
        try:
            if coll.has(d["_key"]):
                coll.update(d)
            else:
                coll.insert(d)
        except Exception as e:  # pragma: no cover
            logger.warning("seed upsert failed for %s/%s: %s", coll_name, d.get("_key"), e)
