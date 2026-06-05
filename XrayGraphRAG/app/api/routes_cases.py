from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import ServiceContainer, get_container
from app.models.schemas import (
    CaseRegisterMetadata,
    CaseRegisterResponse,
    FeedbackRequest,
    SimilaritySearchRequest,
    SimilarCase,
)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseRegisterResponse)
async def register_case(
    image: UploadFile = File(...),
    diseaseTags: str = Form(..., description="JSON array string, e.g. '[\"pneumonia\"]'"),
    findingTags: Optional[str] = Form(None, description="JSON array string"),
    view: Optional[str] = Form("PA"),
    patientAge: Optional[int] = Form(None),
    sex: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    modelVersion: Optional[str] = Form(None),
    maskVersion: Optional[str] = Form(None),
    container: ServiceContainer = Depends(get_container),
) -> CaseRegisterResponse:
    try:
        diseases: List[str] = json.loads(diseaseTags)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"diseaseTags must be JSON array: {e}")
    findings: Optional[List[str]] = None
    if findingTags:
        try:
            findings = json.loads(findingTags)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"findingTags must be JSON array: {e}")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty image upload")

    metadata = CaseRegisterMetadata(
        view=view, patientAge=patientAge, sex=sex, source=source,
        modelVersion=modelVersion, maskVersion=maskVersion,
    )
    result = container.case_service.register_case(
        image_bytes=image_bytes,
        original_filename=image.filename or "upload.png",
        disease_tags=diseases,
        finding_tags=findings,
        metadata=metadata,
    )
    return CaseRegisterResponse(**result)


@router.get("/{case_id}")
def get_case(case_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    doc = container.repo.get_case(case_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")
    return doc


@router.post("/search-similar", response_model=List[SimilarCase])
def search_similar(
    body: SimilaritySearchRequest,
    container: ServiceContainer = Depends(get_container),
) -> List[SimilarCase]:
    return container.repo.vector_search(
        "globalErrorEmbedding",
        body.embedding,
        view=body.view,
        model_version=body.modelVersion,
        mask_version=body.maskVersion,
        top_k=body.topK,
    )


@router.post("/{case_id}/feedback")
def feedback(
    case_id: str,
    body: FeedbackRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    doc = container.repo.get_case(case_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")
    saved = container.repo.add_feedback(case_id, body.model_dump(exclude_none=True))
    return {"status": "saved", "feedback": saved}
