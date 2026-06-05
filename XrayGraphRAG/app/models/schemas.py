"""API/internal Pydantic schema."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- 공통 ----------
class ROIStats(BaseModel):
    meanError: float
    maxError: float
    p95Error: float
    stdError: float = 0.0
    areaRatio: float
    highErrorAreaRatio: float = 0.0
    connectedComponentCount: int = 0
    largestComponentArea: int = 0
    severity: str = "low"  # low|medium|high


class Quality(BaseModel):
    maskQuality: float = 0.9
    imageQuality: float = 0.9
    artifactSuspected: bool = False


# ---------- 등록 입력 ----------
class CaseRegisterMetadata(BaseModel):
    view: Optional[str] = "PA"
    patientAge: Optional[int] = None
    sex: Optional[str] = None
    source: Optional[str] = None
    modelVersion: Optional[str] = None
    maskVersion: Optional[str] = None


# ---------- 등록 응답 ----------
class CaseRegisterResponse(BaseModel):
    caseId: str
    status: str = "created"


# ---------- 케이스 문서 ----------
class CaseDocument(BaseModel):
    key: str = Field(alias="_key")
    imagePath: str
    reconPath: Optional[str] = None
    heatmapPath: Optional[str] = None

    view: str = "PA"
    modelVersion: str
    maskVersion: str
    embeddingVersion: str

    globalErrorEmbedding: List[float]
    leftLungErrorEmbedding: List[float]
    rightLungErrorEmbedding: List[float]
    heartErrorEmbedding: List[float]

    roiStats: Dict[str, ROIStats]
    diseaseTags: List[str] = []
    findingTags: List[str] = []
    quality: Quality = Quality()
    createdAt: str

    model_config = ConfigDict(populate_by_name=True)


# ---------- Search ----------
class SimilaritySearchRequest(BaseModel):
    embedding: List[float]
    view: Optional[str] = None
    modelVersion: Optional[str] = None
    maskVersion: Optional[str] = None
    topK: int = 20


class SimilarCase(BaseModel):
    caseId: str
    similarity: float
    diseaseTags: List[str] = []
    findingTags: List[str] = []
    roiStats: Dict[str, Any] = {}
    imagePath: Optional[str] = None
    heatmapPath: Optional[str] = None


# ---------- Inference ----------
class PredictedDisease(BaseModel):
    disease: str
    score: float
    supportCases: int
    reason: str


class NotableFinding(BaseModel):
    finding: str
    frequencyInSimilarCases: float
    currentCaseEvidence: Dict[str, Any] = {}


class Uncertainty(BaseModel):
    level: str  # low|medium|high
    reasons: List[str] = []


class InferenceResponse(BaseModel):
    queryCase: Dict[str, Any]
    predictedDiseases: List[PredictedDisease]
    notableFindings: List[NotableFinding]
    similarCases: List[SimilarCase]
    uncertainty: Uncertainty
    explanation: Dict[str, Any]
    heatmapPath: Optional[str] = None
    warning: str


# ---------- Feedback ----------
class FeedbackRequest(BaseModel):
    reviewer: Optional[str] = None
    correctedDiseaseTags: Optional[List[str]] = None
    correctedFindingTags: Optional[List[str]] = None
    comment: Optional[str] = None
    approved: Optional[bool] = None
