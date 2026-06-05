#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spring Boot Back-End ↔ prescription_agent 를 연결하는 FastAPI 서비스.

Spring 은 MySQL 에서 환자·진료 기록을 모은 뒤 이 서비스로 POST 합니다.
- `fetch_top_rx_from_arango` 가 true 이고 클라이언트가 보낸 `top_rx` 가 비어 있으면
  ArangoDB(visits → order_lines → prescription_masters) 에서 직접 처방 라인을 채웁니다.
- `disease_codes`(예: E11)가 있고 `fetch_cohort_rx_from_arango` 가 true 이면,
  visit_has_diagnosis 로 해당 상병이 붙은 방문들의 처방을 빈도 집계해 `similar_outcomes` 문구와
  `top_rx` 후보 행(코호트)에 병합합니다.
- 그 외에는 Spring 이 만들어 준 feature 를 그대로 LLM 프롬프트에 싣습니다.
- 응답은 ``prescription_agent.parse_prescriptions_llm_response`` 가 검증한
  Required JSON Format `{ "prescriptions": [...] }` 입니다.

실행:
    cd GraphDB/langchain_graph_qa
    pip install -r requirements.txt
    uvicorn prescription_api:app --host 0.0.0.0 --port 8001
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
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

from prescription_agent import (
    build_prescription_agent_prompt,
    parse_prescriptions_llm_response,
)
from run_prescription_agent import (
    SYSTEM_PRESCRIPTION,
    cohort_stat_rows_to_top_rx_lines,
    fetch_cohort_prescriptions_by_diagnosis_codes,
    fetch_confidence_scores_by_diagnosis_codes,
    fetch_top_rx_from_arango,
    format_cohort_similar_outcomes_summary,
)

logger = logging.getLogger("prescription_api")
logging.basicConfig(
    level=os.environ.get("PRESCRIPTION_API_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


def _load_dotenv_if_present() -> None:
    if not load_dotenv:
        return
    env_file = SCRIPT_DIR / ".env"
    if env_file.is_file():
        # 개발 환경에서 이미 export 된 GOOGLE_API_KEY(구키)가 남아 있으면 .env 값이 무시되는 혼선이 잦다.
        # .env 를 "로컬 단일 진실"로 취급하기 위해 override=True 로 로드한다.
        load_dotenv(env_file, override=True)


_load_dotenv_if_present()

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_TEMPERATURE = float(os.environ.get("GEMINI_TEMPERATURE", "0.0"))


class PrescriptionRecommendRequest(BaseModel):
    """Spring → Python 요청 스키마.

    Spring 은 MySQL 의 History / HistoryDiagnose / HistoryDisease / Patient 를 읽어
    아래 필드로 변환해서 보냅니다. top_rx 가 비어 있으면 `fetch_top_rx_from_arango`
    를 true 로 주어 Arango 에서 보강할 수 있습니다.
    """

    patient_id: str = Field(..., description="Arango 에서 visit·내원번호 매칭에 쓰는 문자열")
    # Python 3.9: Pydantic v2 가 PEP 604 (`|`) 평가에 실패할 수 있어 Union 사용
    symptoms: Union[str, List[Any], Dict[str, Any]] = Field("", description="현재 증상")
    history: Union[str, List[Any], Dict[str, Any]] = Field("", description="과거 진료/특이사항")
    top_rx: Optional[Union[List[Any], str]] = Field(default=None, description="방문의 처방 라인")
    similar_outcomes: Union[str, List[Any], Dict[str, Any]] = Field("", description="유사 환자 요약")
    mention_links: Optional[List[Any]] = None
    clinician_question: Optional[str] = None
    # Spring 기본(ai.prescription-agent.fetch-top-rx-from-arango=true)과 맞춤.
    # 요청 JSON 에 키가 빠져도 Arango 보강을 시도한다.
    fetch_top_rx_from_arango: bool = Field(
        default=True,
        description="true 이고 top_rx 가 비어 있으면 patient_id 로 Arango 조회",
    )
    arango_top_rx_limit: int = Field(default=80, ge=1, le=500)
    disease_codes: Optional[List[str]] = Field(
        default=None,
        description="상병 코드 목록(E11 등). 있으면 Arango에서 코호트 빈도 처방을 조회해 top_rx·similar_outcomes 에 반영",
    )
    fetch_cohort_rx_from_arango: bool = Field(
        default=True,
        description="true 이고 disease_codes 가 비어 있지 않으면 상병별 코호트 처방 통계를 조회",
    )
    arango_cohort_rx_limit: int = Field(default=40, ge=1, le=500)
    model: Optional[str] = None
    temperature: Optional[float] = None


class PrescriptionItem(BaseModel):
    rank: int
    name: str
    prescription_code: str
    dosage: str
    reason: str
    confidence_score: Optional[float] = None


class PrescriptionRecommendResponse(BaseModel):
    prescriptions: List[PrescriptionItem]
    used_arango_top_rx: bool = False
    arango_top_rx_count: int = 0
    used_cohort_rx: bool = False
    cohort_rx_count: int = 0


class PrescriptionFeedbackItem(BaseModel):
    rank: int
    prescription_id: Optional[int] = None
    prescription_code: str
    prescription_name: str
    confidence_score: Optional[float] = None
    reason: Optional[str] = None
    status: str


class PrescriptionFeedbackRequest(BaseModel):
    history_id: int
    history_diagnose_id: Optional[int] = None
    feedback_items: List[PrescriptionFeedbackItem]


class PrescriptionFeedbackResponse(BaseModel):
    saved: int
    edge_collection: str


app = FastAPI(
    title="BitComputer Prescription Agent",
    version="0.1.0",
    description="ArangoDB 그래프 + Gemini 기반 처방 추천 에이전트 (Spring Boot 연동용).",
)

_ARANGO_HISTORY_VTX = "recommendation_histories"
_ARANGO_FALLBACK_RX_VTX = "recommendation_prescriptions"
_ARANGO_RECOMMENDED_EDGE = "history_recommended_prescription"


@app.get("/")
def root() -> Dict[str, Any]:
    """브라우저로 루트만 열 때 404로 오해하지 않도록 안내."""
    return {
        "service": "prescription_api",
        "message": "Spring에서 호출하는 처방 추천 API입니다. 웹 화면 URL이 아닙니다.",
        "health": "/health",
        "openapi_docs": "/docs",
        "recommend_endpoint": "POST /api/agent/prescription/recommend",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "google_api_key_set": bool(os.environ.get("GOOGLE_API_KEY")),
        # 환경변수가 있어도 Google 에서 거절(API_KEY_INVALID)할 수 있음 — 유효성은 /health 로 판단 불가
        "google_api_key_note": "non_empty env only; validity is checked on first /recommend (Gemini)",
        "default_model": DEFAULT_MODEL,
        "arangodb_expected": (
            f"{os.environ.get('ARANGO_HOST', '127.0.0.1')}:"
            f"{os.environ.get('ARANGO_PORT', '8529')} "
            "(optional; cohort/top_rx graph queries skip if down)"
        ),
    }


def _normalize_disease_codes(raw: Optional[List[str]]) -> List[str]:
    if not raw:
        return []
    return [str(c).strip() for c in raw if c is not None and str(c).strip()]


def _merge_top_rx_with_cohort(
    base: Any,
    cohort_lines: List[Dict[str, Any]],
) -> List[Any]:
    """환자 방문 처방 뒤에 코호트 후보를 붙인다(처방코드 중복은 스킵)."""
    base_list: List[Any] = []
    if isinstance(base, list):
        base_list = list(base)
    seen_codes: set[str] = set()
    for row in base_list:
        if isinstance(row, dict):
            c = row.get("prescription_code")
            if c is None:
                c = row.get("처방코드")
            if c is not None and str(c).strip():
                seen_codes.add(str(c).strip())
    out = list(base_list)
    for row in cohort_lines:
        c = row.get("prescription_code") if isinstance(row, dict) else None
        if c is None and isinstance(row, dict):
            c = row.get("처방코드")
        key = str(c).strip() if c is not None else ""
        if key and key in seen_codes:
            continue
        if key:
            seen_codes.add(key)
        out.append(row)
    return out


def _combine_similar_outcomes(base: Any, cohort_summary: str) -> str:
    parts: List[str] = []
    if isinstance(base, str) and base.strip():
        parts.append(base.strip())
    elif base not in (None, "", []):
        parts.append(str(base).strip())
    if cohort_summary.strip():
        parts.append(cohort_summary.strip())
    return "\n\n".join(parts) if parts else ""


def _is_empty_top_rx(top_rx: Any) -> bool:
    if top_rx is None:
        return True
    if isinstance(top_rx, str):
        return not top_rx.strip()
    if isinstance(top_rx, (list, tuple, dict)):
        return len(top_rx) == 0
    return False


def _safe_key_part(raw: Any, fallback: str) -> str:
    text = str(raw).strip() if raw is not None else ""
    if not text:
        text = fallback
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)


def _get_arango_db():
    from run_graph_qa import connect_arango, load_arango_config

    cfg = load_arango_config()
    return connect_arango(cfg)


def _ensure_feedback_graph_collections(db: Any) -> None:
    if not db.has_collection(_ARANGO_HISTORY_VTX):
        db.create_collection(_ARANGO_HISTORY_VTX)
    if not db.has_collection(_ARANGO_FALLBACK_RX_VTX):
        db.create_collection(_ARANGO_FALLBACK_RX_VTX)
    if not db.has_collection(_ARANGO_RECOMMENDED_EDGE):
        db.create_collection(_ARANGO_RECOMMENDED_EDGE, edge=True)


@app.post(
    "/api/agent/prescription/recommend",
    response_model=PrescriptionRecommendResponse,
)
def recommend(req: PrescriptionRecommendRequest) -> PrescriptionRecommendResponse:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY 가 설정되지 않았습니다. 서버 환경변수 또는 .env 를 확인하세요.",
        )

    effective_top_rx: Any = req.top_rx
    used_arango = False
    arango_count = 0
    used_cohort = False
    cohort_count = 0

    dx_codes = _normalize_disease_codes(req.disease_codes)

    _tr_len = len(req.top_rx) if isinstance(req.top_rx, list) else ("str" if isinstance(req.top_rx, str) else "?")
    logger.info(
        "recommend: patient_id=%r fetch_top_rx_from_arango=%s top_rx=%s disease_codes=%s",
        req.patient_id,
        req.fetch_top_rx_from_arango,
        _tr_len,
        dx_codes,
    )

    # confidence_score 는 LLM 출력에 없으므로, Arango co-occurrence 기반으로 별도 계산한다.
    w_freq = float(os.environ.get("CONFIDENCE_W_FREQ", "0.7"))
    w_sim = float(os.environ.get("CONFIDENCE_W_SIM", "0.3"))
    accepted_boost = float(os.environ.get("CONFIDENCE_ACCEPTED_BOOST", "0.15"))
    rejected_penalty = float(os.environ.get("CONFIDENCE_REJECTED_PENALTY", "0.20"))
    missed_boost = float(os.environ.get("CONFIDENCE_MISSED_BOOST", "0.05"))
    feedback_smoothing = float(os.environ.get("CONFIDENCE_FEEDBACK_SMOOTHING", "5.0"))
    confidence_by_code: dict[str, float] = {}
    if dx_codes:
        try:
            # NOTE: confidence AQL이 상위 N개만 반환하므로, LLM이 고른 코드가 누락되지 않도록 넉넉히 조회한다.
            confidence_rows = fetch_confidence_scores_by_diagnosis_codes(
                dx_codes,
                limit=int(os.environ.get("CONFIDENCE_LIMIT", str(max(5000, req.arango_cohort_rx_limit * 50)))),
                w_freq=w_freq,
                w_sim=w_sim,
                accepted_boost=accepted_boost,
                rejected_penalty=rejected_penalty,
                missed_boost=missed_boost,
                feedback_smoothing=feedback_smoothing,
            )
            confidence_by_code = {
                str(r.get("prescription_code")): float(r.get("confidence_score") or 0.0)
                for r in (confidence_rows or [])
                if r.get("prescription_code") is not None
            }
        except Exception as exc:
            logger.warning("confidence_score 계산 실패: %s", exc)

    if req.fetch_top_rx_from_arango and _is_empty_top_rx(effective_top_rx):
        try:
            rows = fetch_top_rx_from_arango(
                req.patient_id, limit=req.arango_top_rx_limit
            )
        except Exception as exc:  # Arango 연결/AQL 실패는 500 이 아니라 경고 후 원본 유지
            logger.warning(
                "Arango top_rx 조회 실패 (patient_id=%r): %s", req.patient_id, exc
            )
            rows = []
        if rows:
            effective_top_rx = rows
            used_arango = True
            arango_count = len(rows)
            logger.info(
                "Arango 에서 top_rx %d 건 로드 (patient_id=%r)", arango_count, req.patient_id
            )
        else:
            logger.info(
                "Arango 에서 top_rx 를 찾지 못함 (patient_id=%r). 요청의 top_rx 를 그대로 사용.",
                req.patient_id,
            )

    cohort_summary = ""
    if req.fetch_cohort_rx_from_arango and dx_codes:
        try:
            cohort_stats = fetch_cohort_prescriptions_by_diagnosis_codes(
                dx_codes,
                limit=req.arango_cohort_rx_limit,
            )
        except Exception as exc:
            logger.warning("코호트 처방 조회 실패 (codes=%r): %s", dx_codes, exc)
            cohort_stats = []
        if cohort_stats:
            used_cohort = True
            cohort_count = len(cohort_stats)
            cohort_lines = cohort_stat_rows_to_top_rx_lines(cohort_stats)
            effective_top_rx = _merge_top_rx_with_cohort(effective_top_rx, cohort_lines)
            cohort_summary = format_cohort_similar_outcomes_summary(dx_codes, cohort_stats)
            logger.info(
                "상병 코호트 처방 %d건 병합 (codes=%r)",
                cohort_count,
                dx_codes,
            )

    similar_for_prompt = _combine_similar_outcomes(req.similar_outcomes, cohort_summary)

    if _is_empty_top_rx(effective_top_rx):
        effective_top_rx = [{"note": "데이터 부족: top_rx 비어 있음"}]

    user_msg = build_prescription_agent_prompt(
        patient_id=req.patient_id,
        symptoms=req.symptoms,
        history=req.history,
        top_rx=effective_top_rx,
        similar_outcomes=similar_for_prompt,
        clinician_question=req.clinician_question,
        mention_links=req.mention_links,
    )

    model_id = req.model or DEFAULT_MODEL
    temperature = (
        req.temperature if req.temperature is not None else DEFAULT_TEMPERATURE
    )
    llm = ChatGoogleGenerativeAI(model=model_id, temperature=temperature)

    try:
        resp = llm.invoke(
            [
                ("system", SYSTEM_PRESCRIPTION),
                ("human", user_msg),
            ]
        )
    except ChatGoogleGenerativeAIError as exc:
        logger.exception("Gemini 호출 실패")
        msg = str(exc)
        if "PERMISSION_DENIED" in msg or "403" in msg:
            # 키 유출(leaked) 신고로 차단되는 케이스가 실제로 자주 발생한다.
            # 사용자에게 "키 재발급/교체"가 필요하다는 힌트를 주기 위해 상태코드를 구분한다.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini 권한 오류(PERMISSION_DENIED)로 호출이 차단되었습니다. "
                    "대부분 API 키가 만료/비활성화되었거나 '유출(leaked)로 신고'되어 폐기된 경우입니다. "
                    "새 GOOGLE_API_KEY 로 교체한 뒤 다시 시도하세요."
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=f"Gemini 호출 실패: {exc}") from exc

    raw = (resp.content or "").strip() if hasattr(resp, "content") else str(resp).strip()

    try:
        data = parse_prescriptions_llm_response(raw)
    except ValueError as exc:
        logger.error("LLM 응답 파싱 실패: %s / raw=%r", exc, raw)
        raise HTTPException(status_code=502, detail=f"LLM JSON 파싱 실패: {exc}") from exc

    items = [PrescriptionItem(**item) for item in data["prescriptions"]]

    # confidence_by_code는 Arango co-occurrence 기반 계산 결과.
    # LLM 출력에는 confidence_score가 없으므로 처방코드로 매칭해서 주입한다.
    for it in items:
        if not it.prescription_code:
            continue
        code = str(it.prescription_code).strip()
        if not code or code == "미기재":
            continue
        if confidence_by_code:
            it.confidence_score = confidence_by_code.get(code, 0.0)

    return PrescriptionRecommendResponse(
        prescriptions=items,
        used_arango_top_rx=used_arango,
        arango_top_rx_count=arango_count,
        used_cohort_rx=used_cohort,
        cohort_rx_count=cohort_count,
    )


@app.post(
    "/api/agent/prescription/feedback",
    response_model=PrescriptionFeedbackResponse,
)
def save_feedback(req: PrescriptionFeedbackRequest) -> PrescriptionFeedbackResponse:
    if not req.feedback_items:
        raise HTTPException(status_code=400, detail="feedback_items 가 비어 있습니다.")
    try:
        db = _get_arango_db()
        _ensure_feedback_graph_collections(db)
    except Exception as exc:
        logger.exception("ArangoDB 연결 또는 컬렉션 준비 실패")
        raise HTTPException(status_code=502, detail=f"ArangoDB 처리 실패: {exc}") from exc

    now_iso = datetime.now(timezone.utc).isoformat()
    history_col = db.collection(_ARANGO_HISTORY_VTX)
    fallback_rx_col = db.collection(_ARANGO_FALLBACK_RX_VTX)
    edge_col = db.collection(_ARANGO_RECOMMENDED_EDGE)

    history_key = _safe_key_part(req.history_id, "history")
    history_doc_id = f"{_ARANGO_HISTORY_VTX}/{history_key}"
    history_col.insert(
        {
            "_key": history_key,
            "history_id": req.history_id,
            "history_diagnose_id": req.history_diagnose_id,
            "updated_at": now_iso,
        },
        overwrite=True,
        silent=True,
    )

    saved_count = 0
    for item in req.feedback_items:
        rx_code_key = _safe_key_part(item.prescription_code, "unknown_code")
        rank_key = _safe_key_part(item.rank, "0")
        edge_key = f"{history_key}_{rank_key}_{rx_code_key}"

        target_doc_id = f"prescription_masters/{rx_code_key}"
        if not db.has_document(target_doc_id):
            fallback_rx_col.insert(
                {
                    "_key": rx_code_key,
                    "prescription_code": item.prescription_code,
                    "prescription_name": item.prescription_name,
                    "updated_at": now_iso,
                },
                overwrite=True,
                silent=True,
            )
            target_doc_id = f"{_ARANGO_FALLBACK_RX_VTX}/{rx_code_key}"

        edge_col.insert(
            {
                "_key": edge_key,
                "_from": history_doc_id,
                "_to": target_doc_id,
                "history_id": req.history_id,
                "history_diagnose_id": req.history_diagnose_id,
                "rank": item.rank,
                "prescription_id": item.prescription_id,
                "prescription_code": item.prescription_code,
                "prescription_name": item.prescription_name,
                "confidence_score": item.confidence_score,
                "reason": item.reason,
                "status": item.status,
                "updated_at": now_iso,
            },
            overwrite=True,
            silent=True,
        )
        saved_count += 1

    logger.info(
        "Arango 처방 피드백 저장 완료: history_id=%s saved=%s edge_collection=%s",
        req.history_id,
        saved_count,
        _ARANGO_RECOMMENDED_EDGE,
    )
    return PrescriptionFeedbackResponse(
        saved=saved_count,
        edge_collection=_ARANGO_RECOMMENDED_EDGE,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "prescription_api:app",
        host=os.environ.get("PRESCRIPTION_API_HOST", "0.0.0.0"),
        port=int(os.environ.get("PRESCRIPTION_API_PORT", "8001")),
        reload=bool(os.environ.get("PRESCRIPTION_API_RELOAD", "")),
    )
