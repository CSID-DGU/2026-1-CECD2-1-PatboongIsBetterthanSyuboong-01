#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spring Boot Back-End ↔ Gemini 기반 진단서 소견 생성 FastAPI 서비스.

Spring은 MySQL에서 환자·진료 기록을 모은 뒤 이 서비스로 POST합니다.
응답: {"medicalCertificate": "..."} — 진단서 소견 텍스트

prescription_api.py 와 동일한 구조로 작성됨.

실행:
    cd GraphDB/langchain_graph_qa
    pip install -r requirements.txt
    # 영상판독 Flask 서버(AI_BackEnd/app.py)와 포트 충돌을 피하려고 5001 사용.
    # Spring 의 application.properties 의 ai.certificate-agent.base-url 과 일치해야 한다.
    uvicorn certificate_api:app --host 0.0.0.0 --port 5001
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from certificate_agent import SYSTEM_CERTIFICATE, build_certificate_agent_prompt

logger = logging.getLogger("certificate_api")
logging.basicConfig(
    level=os.environ.get("CERTIFICATE_API_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


def _load_dotenv_if_present() -> None:
    if not load_dotenv:
        return
    env_file = SCRIPT_DIR / ".env"
    if env_file.is_file():
        load_dotenv(env_file)


_load_dotenv_if_present()

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
DEFAULT_TEMPERATURE = float(os.environ.get("GEMINI_TEMPERATURE", "0.3"))


# ── Request / Response 스키마 ─────────────────────────────────────────────────

class DiseaseInfo(BaseModel):
    code: str = ""
    name: str = ""
    degree: str | None = None


class DiagnoseInfo(BaseModel):
    code: str = ""
    name: str = ""
    dose: int = 0
    time: int = 0
    days: int = 0


class CertificateGenerateRequest(BaseModel):
    """Spring → Python 요청 스키마.

    Spring의 CertificateAgentRequest 와 필드명이 1:1 로 매칭된다.
    """
    history_id: int
    certificate_type: str = Field(default="GENERAL", description="GENERAL 또는 MILITARY")
    patient_name: str = ""
    patient_age: int = 0
    patient_gender: str = ""
    entry_date: str = ""
    symptom_detail: str | None = None
    diagnosis_kind: str = Field(default="미선택", description="임상적 추정 또는 최종 진단")
    purpose: str = Field(default="", description="진단서 용도")
    diseases: list[DiseaseInfo] = Field(default_factory=list)
    diagnoses: list[DiagnoseInfo] = Field(default_factory=list)


class CertificateGenerateResponse(BaseModel):
    medicalCertificate: str


# ── FastAPI 앱 ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BitComputer Certificate Generation Agent",
    version="0.1.0",
    description="Gemini 기반 진단서 소견 생성 서비스 (Spring Boot 연동용).",
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "google_api_key_set": bool(os.environ.get("GOOGLE_API_KEY")),
        "default_model": DEFAULT_MODEL,
    }


@app.post("/api/ai/document/generate", response_model=CertificateGenerateResponse)
def generate_certificate(req: CertificateGenerateRequest) -> CertificateGenerateResponse:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY 가 설정되지 않았습니다. 서버 환경변수 또는 .env 를 확인하세요.",
        )

    user_msg = build_certificate_agent_prompt(
        patient_gender=req.patient_gender,
        patient_age=req.patient_age,
        entry_date=req.entry_date,
        symptom_detail=req.symptom_detail,
        diagnosis_kind=req.diagnosis_kind,
        purpose=req.purpose,
        diseases=[d.model_dump() for d in req.diseases],
        diagnoses=[d.model_dump() for d in req.diagnoses],
        certificate_type=req.certificate_type,
    )

    logger.info(
        "진단서 생성 요청 - history_id=%d, type=%s",
        req.history_id,
        req.certificate_type,
    )

    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE)

    try:
        resp = llm.invoke(
            [
                ("system", SYSTEM_CERTIFICATE),
                ("human", user_msg),
            ]
        )
    except ChatGoogleGenerativeAIError as exc:
        logger.exception("Gemini 호출 실패 - history_id=%d", req.history_id)
        raise HTTPException(status_code=502, detail=f"Gemini 호출 실패: {exc}") from exc

    certificate = (
        resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
    )

    logger.info(
        "진단서 생성 완료 - history_id=%d, length=%d", req.history_id, len(certificate)
    )
    return CertificateGenerateResponse(medicalCertificate=certificate)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "certificate_api:app",
        host=os.environ.get("CERTIFICATE_API_HOST", "0.0.0.0"),
        port=int(os.environ.get("CERTIFICATE_API_PORT", "5001")),
        reload=bool(os.environ.get("CERTIFICATE_API_RELOAD", "")),
    )
