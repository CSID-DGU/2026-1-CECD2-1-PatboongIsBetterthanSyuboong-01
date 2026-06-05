from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import ServiceContainer, get_container
from app.models.schemas import InferenceResponse

router = APIRouter(tags=["inference"])


@router.post("/infer", response_model=InferenceResponse)
async def infer(
    image: UploadFile = File(...),
    view: Optional[str] = Form(None),
    modelVersion: Optional[str] = Form(None),
    maskVersion: Optional[str] = Form(None),
    topK: int = Form(20),
    container: ServiceContainer = Depends(get_container),
) -> InferenceResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty image upload")
    return container.case_service.infer(
        image_bytes=image_bytes,
        view=view,
        model_version=modelVersion,
        mask_version=maskVersion,
        top_k=topK,
    )
