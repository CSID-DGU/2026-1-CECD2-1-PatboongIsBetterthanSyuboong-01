#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
처방 추천 프롬프트(prescription_agent)를 Gemini에 보내 JSON 응답을 받습니다.

기본: -f JSON 안의 top_rx·similar_outcomes·mention_links 를 그대로 프롬프트에 넣습니다. (Arango 미호출)

선택: ``--fetch-top-rx-from-arango`` 를 켜면 JSON의 ``patient_id``(내원번호 또는 VISIT_ 접두 방문키)로
ArangoDB에서 ``visit_has_order`` → ``order_lines`` → ``order_refers_prescription`` 경로를 읽어
``top_rx`` 를 덮어씁니다. 연결 정보는 ``run_graph_qa.py`` 와 동일(환경 변수·Spring local properties).

  cd GraphDB/langchain_graph_qa
  python run_prescription_agent.py -f patient_ctx.example.json
  python run_prescription_agent.py -f patient_ctx.example.json --fetch-top-rx-from-arango
  python run_prescription_agent.py -f patient_ctx.visit_530524451.json
  python run_prescription_agent.py -f patient_ctx.example.json -q "NSAID는 피하고 싶습니다"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

if sys.version_info < (3, 9):
    print(
        "[오류] Python 3.9 이상이 필요합니다 (langchain-google-genai).",
        file=sys.stderr,
    )
    raise SystemExit(1)

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
    load_prescription_context_file,
    parse_prescriptions_llm_response,
)

SYSTEM_PRESCRIPTION = (
    "당신은 지시에 따르는 의료 데이터 분석 보조 도구입니다. "
    "사용자 메시지의 형식과 제약을 정확히 따르고, 요구된 JSON 외 문장은 출력하지 마십시오. "
    "처방명(name)은 사용자 메시지의 top_rx 목록에 있을 때 반드시 그 문자열을 따르고, "
    "일반 의학 지식은 reason 등 설명에만 짧게 사용하십시오."
)


def _load_dotenv_if_present() -> None:
    if not load_dotenv:
        return
    env_file = SCRIPT_DIR / ".env"
    if env_file.is_file():
        # 셸에 남아있는 구키(export GOOGLE_API_KEY)로 인해 .env 값이 무시되는 경우를 방지.
        load_dotenv(env_file, override=True)


def fetch_top_rx_from_arango(patient_id: Any, *, limit: int = 80) -> list[dict[str, Any]]:
    """
    patient_id: 내원번호(숫자 문자열) 또는 visits.visit_id / _key 형태 (예: VISIT_530524451).

    Returns:
        order_lines + prescription_masters 요약 행 리스트 (비면 DB에 방문·처방 없음).
    """
    import logging

    _log = logging.getLogger("run_prescription_agent")

    raw = str(patient_id).strip()
    if not raw:
        return []
    vid_key = raw if raw.upper().startswith("VISIT_") else f"VISIT_{raw}"
    aql = """
    WITH visits, visit_has_order, order_lines, prescription_masters, order_refers_prescription
    FOR v IN visits
      FILTER v.`내원번호_norm` == @pid OR v.visit_id == @vid_key OR v._key == @vid_key
      FOR vo IN visit_has_order
        FILTER vo._from == v._id
        LET ol = DOCUMENT(vo._to)
        LET pm = FIRST(
          FOR orp IN order_refers_prescription
            FILTER orp._from == ol._id
            RETURN DOCUMENT(orp._to)
        )
        SORT ol.`처방시퀀스_norm`
        LIMIT @limit
        RETURN {
          visit_id: v.visit_id,
          "내원번호": v.`내원번호_norm`,
          "처방시퀀스": ol.`처방시퀀스_norm`,
          "처방코드": ol.`처방코드_norm`,
          "처방명": ol.`처방명_norm`,
          prescription_code: pm.prescription_code,
          canonical_name: pm.canonical_name,
          order_line_id: ol.order_line_id
        }
    """
    try:
        from run_graph_qa import _aql_rows, connect_arango, load_arango_config

        cfg = load_arango_config()
        try:
            db = connect_arango(cfg)
        except SystemExit as e:
            # connect_arango() 는 실패 시 SystemExit(2) — FastAPI 에서는 빈 결과로 폴백
            _log.warning(
                "ArangoDB 연결 실패(Docker/8529·application-local.properties 확인). SystemExit: %s",
                e,
            )
            return []
        rows = _aql_rows(db, aql, {"pid": raw, "vid_key": vid_key, "limit": limit})
        if not rows:
            _log.info(
                "Arango top_rx 0건 (patient_id=%r, pid=%r, vid_key=%r) — 그래프에 방문·처방 없거나 내원번호 불일치",
                patient_id,
                raw,
                vid_key,
            )
        return rows
    except Exception as exc:
        _log.warning("Arango top_rx 조회 예외: %s", exc, exc_info=True)
        return []


_COHORT_AQL = """
WITH visits, diagnoses, visit_has_diagnosis, visit_has_order, order_lines,
     prescription_masters, order_refers_prescription
LET pairs = (
  FOR vhd IN visit_has_diagnosis
    LET dx = DOCUMENT(vhd._to)
    FILTER dx != null AND (
      dx.`상병코드_norm` IN @codes OR
      SPLIT(vhd._to, '/')[1] IN @codes
    )
    LET v = DOCUMENT(vhd._from)
    FILTER v != null
    FOR vo IN visit_has_order
      FILTER vo._from == v._id
      LET ol = DOCUMENT(vo._to)
      FILTER ol != null
      LET pm = FIRST(
        FOR orp IN order_refers_prescription
          FILTER orp._from == ol._id
          RETURN DOCUMENT(orp._to)
      )
      LET pcode = (
        pm != null AND pm.prescription_code != null
        AND LENGTH(TRIM(TO_STRING(pm.prescription_code))) > 0
      ) ? pm.prescription_code : ol.`처방코드_norm`
      LET pname = (
        pm != null AND pm.canonical_name != null
        AND LENGTH(TRIM(TO_STRING(pm.canonical_name))) > 0
      ) ? pm.canonical_name : ol.`처방명_norm`
      FILTER pcode != null OR pname != null
      RETURN { pc: pcode, pn: pname }
)
FOR p IN pairs
  COLLECT pc = p.pc, pn = p.pn WITH COUNT INTO cnt
  SORT cnt DESC
  LIMIT @limit
  RETURN {
    prescription_code: pc,
    canonical_name: pn,
    cohort_prescription_count: cnt
  }
"""


def fetch_cohort_prescriptions_by_diagnosis_codes(
    disease_codes: list[str],
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """
    상병 코드(예: E11)가 visit_has_diagnosis 로 연결된 방문들에서,
    함께 나타난 처방(order_line)을 처방코드·처방명 기준으로 빈도 집계한다.

    Args:
        disease_codes: 정규화된 상병코드 문자열 목록 (공백 제거 권장).
        limit: 반환할 상위 N개 처방 통계.

    Returns:
        cohort_prescription_count 내림차순 행 리스트. 연결 실패 시 [].
    """
    import logging

    _log = logging.getLogger("run_prescription_agent")

    codes = [str(c).strip() for c in disease_codes if c is not None and str(c).strip()]
    if not codes:
        return []

    try:
        from run_graph_qa import _aql_rows, connect_arango, load_arango_config

        cfg = load_arango_config()
        try:
            db = connect_arango(cfg)
        except SystemExit as e:
            _log.warning(
                "ArangoDB 연결 실패(상병 코호트 조회). SystemExit: %s",
                e,
            )
            return []
        rows = _aql_rows(db, _COHORT_AQL, {"codes": codes, "limit": int(limit)})
        if not rows:
            _log.info(
                "상병 코호트 처방 0건 (codes=%r) — 그래프에 해당 상병·처방 경로 없음",
                codes,
            )
        return list(rows) if rows else []
    except Exception as exc:
        _log.warning("상병 코호트 AQL 예외: %s", exc, exc_info=True)
        return []


def fetch_confidence_scores_by_diagnosis_codes(
    disease_codes: list[str],
    *,
    limit: int = 200,
    w_freq: float = 0.7,
    w_sim: float = 0.3,
    accepted_boost: float = 0.15,
    rejected_penalty: float = 0.2,
    missed_boost: float = 0.05,
    feedback_smoothing: float = 5.0,
) -> list[dict[str, Any]]:
    """
    confidence_score = w_freq * S_freq + w_sim * S_similarity + feedback_adjustment

    - S_freq: (해당 질병코드 중 하나라도 포함한 방문들 중) 처방 M이 등장한 방문 비율
    - S_similarity: (해당 질병코드를 모두 포함한 방문들 중) 처방 M이 등장한 방문 비율
    - feedback_adjustment:
      accepted 비율은 점수 가산, rejected 비율은 감산, missed 비율은 소폭 가산
      (표본 수가 적을 때 과보정 방지를 위해 smoothing 적용)

    각 값은 방문 단위 co-occurrence로 계산하므로 0~1 범위에 들어가도록 설계.
    """
    import logging

    _log = logging.getLogger("run_prescription_agent")
    codes = [str(c).strip() for c in disease_codes if c is not None and str(c).strip()]
    if not codes:
        return []

    w_sum = float(w_freq + w_sim)
    if w_sum <= 0:
        w_freq, w_sim = 0.5, 0.5
    else:
        w_freq = float(w_freq) / w_sum
        w_sim = float(w_sim) / w_sum

    try:
        from run_graph_qa import _aql_rows, connect_arango, load_arango_config

        cfg = load_arango_config()
        try:
            db = connect_arango(cfg)
        except SystemExit as e:
            _log.warning("ArangoDB 연결 실패(confidence 계산). SystemExit: %s", e)
            return []

        # 1) union: 방문이 '코드 중 하나라도' 포함
        aql_union = """
        WITH visits, visit_has_diagnosis, diagnoses, visit_has_order, order_lines, prescription_masters, order_refers_prescription
        LET codes = @codes
        LET union_total = (
          FOR v IN visits
            LET has_any = LENGTH(
              FOR vhd IN visit_has_diagnosis
                FILTER vhd._from == v._id
                LET dx = DOCUMENT(vhd._to)
                FILTER dx != null AND (
                  dx.`상병코드_norm` IN codes OR SPLIT(vhd._to, '/')[1] IN codes
                )
                LIMIT 1
                RETURN 1
            )
            FILTER has_any > 0
            RETURN 1
        )
        LET union_total_count = LENGTH(union_total)

        LET rows = (
          FOR v IN visits
            LET has_any = LENGTH(
              FOR vhd IN visit_has_diagnosis
                FILTER vhd._from == v._id
                LET dx = DOCUMENT(vhd._to)
                FILTER dx != null AND (
                  dx.`상병코드_norm` IN codes OR SPLIT(vhd._to, '/')[1] IN codes
                )
                LIMIT 1
                RETURN 1
            )
            FILTER has_any > 0

            FOR vo IN visit_has_order
              FILTER vo._from == v._id
              LET ol = DOCUMENT(vo._to)
              LET pm = FIRST(
                FOR orp IN order_refers_prescription
                  FILTER orp._from == ol._id
                  RETURN DOCUMENT(orp._to)
              )

              LET pcode = (
                pm != null AND pm.prescription_code != null
                AND LENGTH(TRIM(TO_STRING(pm.prescription_code))) > 0
              ) ? pm.prescription_code : ol.`처방코드_norm`

              LET pname = (
                pm != null AND pm.canonical_name != null
                AND LENGTH(TRIM(TO_STRING(pm.canonical_name))) > 0
              ) ? pm.canonical_name : ol.`처방명_norm`

              FILTER pcode != null OR pname != null

              COLLECT pc = pcode, pn = pname, vId = v._id
              RETURN { pc: pc, pn: pn, vId: vId }
        )

        FOR r IN rows
          COLLECT pc = r.pc, pn = r.pn WITH COUNT INTO cnt
          LET s_freq = union_total_count > 0 ? cnt / union_total_count : 0
          SORT s_freq DESC
          LIMIT @limit
          RETURN {
            prescription_code: pc,
            canonical_name: pn,
            union_visits: cnt,
            s_freq: s_freq
          }
        """
        union_rows = _aql_rows(db, aql_union, {"codes": codes, "limit": int(limit)})
        if not union_rows:
            return []

        # 2) all: 방문이 '모든 코드'를 포함
        aql_all = """
        WITH visits, visit_has_diagnosis, diagnoses, visit_has_order, order_lines, prescription_masters, order_refers_prescription
        LET codes = @codes
        LET all_total = (
          FOR v IN visits
            LET presentCodes = UNIQUE(
              FOR vhd IN visit_has_diagnosis
                FILTER vhd._from == v._id
                LET dx = DOCUMENT(vhd._to)
                FILTER dx != null AND (
                  dx.`상병코드_norm` IN codes OR SPLIT(vhd._to, '/')[1] IN codes
                )
                RETURN (
                  dx.`상병코드_norm` != null ? dx.`상병코드_norm` : SPLIT(vhd._to, '/')[1]
                )
            )
            FILTER LENGTH(presentCodes) == LENGTH(codes)
            RETURN 1
        )
        LET all_total_count = LENGTH(all_total)

        LET rows = (
          FOR v IN visits
            LET presentCodes = UNIQUE(
              FOR vhd IN visit_has_diagnosis
                FILTER vhd._from == v._id
                LET dx = DOCUMENT(vhd._to)
                FILTER dx != null AND (
                  dx.`상병코드_norm` IN codes OR SPLIT(vhd._to, '/')[1] IN codes
                )
                RETURN (
                  dx.`상병코드_norm` != null ? dx.`상병코드_norm` : SPLIT(vhd._to, '/')[1]
                )
            )
            FILTER LENGTH(presentCodes) == LENGTH(codes)

            FOR vo IN visit_has_order
              FILTER vo._from == v._id
              LET ol = DOCUMENT(vo._to)
              LET pm = FIRST(
                FOR orp IN order_refers_prescription
                  FILTER orp._from == ol._id
                  RETURN DOCUMENT(orp._to)
              )
              LET pcode = (
                pm != null AND pm.prescription_code != null
                AND LENGTH(TRIM(TO_STRING(pm.prescription_code))) > 0
              ) ? pm.prescription_code : ol.`처방코드_norm`
              LET pname = (
                pm != null AND pm.canonical_name != null
                AND LENGTH(TRIM(TO_STRING(pm.canonical_name))) > 0
              ) ? pm.canonical_name : ol.`처방명_norm`
              FILTER pcode != null OR pname != null
              COLLECT pc = pcode, pn = pname, vId = v._id
              RETURN { pc: pc, pn: pn, vId: vId }
        )

        FOR r IN rows
          COLLECT pc = r.pc, pn = r.pn WITH COUNT INTO cnt
          LET s_similarity = all_total_count > 0 ? cnt / all_total_count : 0
          SORT s_similarity DESC
          LIMIT @limit
          RETURN {
            prescription_code: pc,
            canonical_name: pn,
            all_visits: cnt,
            s_similarity: s_similarity
          }
        """

        all_rows = _aql_rows(db, aql_all, {"codes": codes, "limit": int(limit)})

        sim_by_code: dict[str, float] = {}
        for r in all_rows or []:
            code = r.get("prescription_code")
            if code is None:
                continue
            sim_by_code[str(code)] = float(r.get("s_similarity") or 0.0)

        feedback_by_code: dict[str, dict[str, float]] = {}
        if db.has_collection("history_recommended_prescription"):
            aql_feedback = """
            FOR e IN history_recommended_prescription
              FILTER e.prescription_code != null
                AND e.status IN ["accepted", "rejected", "missed"]
              COLLECT pc = e.prescription_code
              AGGREGATE
                total = COUNT(e),
                accepted = SUM(e.status == "accepted" ? 1 : 0),
                rejected = SUM(e.status == "rejected" ? 1 : 0),
                missed = SUM(e.status == "missed" ? 1 : 0)
              RETURN {
                prescription_code: pc,
                total: total,
                accepted: accepted,
                rejected: rejected,
                missed: missed
              }
            """
            fb_rows = _aql_rows(db, aql_feedback)
            for r in fb_rows or []:
                code = r.get("prescription_code")
                if code is None:
                    continue
                feedback_by_code[str(code)] = {
                    "total": float(r.get("total") or 0.0),
                    "accepted": float(r.get("accepted") or 0.0),
                    "rejected": float(r.get("rejected") or 0.0),
                    "missed": float(r.get("missed") or 0.0),
                }

        out: list[dict[str, Any]] = []
        for r in union_rows:
            code = r.get("prescription_code")
            if code is None:
                continue
            code_s = str(code)
            s_freq = float(r.get("s_freq") or 0.0)
            s_sim = sim_by_code.get(code_s, 0.0)
            base_score = (w_freq * s_freq) + (w_sim * s_sim)

            fb = feedback_by_code.get(code_s)
            feedback_adjustment = 0.0
            feedback_total = 0.0
            if fb:
                feedback_total = float(fb.get("total") or 0.0)
                if feedback_total > 0:
                    accepted_rate = float(fb.get("accepted") or 0.0) / feedback_total
                    rejected_rate = float(fb.get("rejected") or 0.0) / feedback_total
                    missed_rate = float(fb.get("missed") or 0.0) / feedback_total
                    raw_adj = (
                        (accepted_boost * accepted_rate)
                        - (rejected_penalty * rejected_rate)
                        + (missed_boost * missed_rate)
                    )
                    shrink = feedback_total / (feedback_total + max(feedback_smoothing, 1e-9))
                    feedback_adjustment = raw_adj * shrink

            score_total = min(1.0, max(0.0, base_score + feedback_adjustment))
            out.append(
                {
                    "prescription_code": code_s,
                    "canonical_name": r.get("canonical_name") or "",
                    "s_freq": s_freq,
                    "s_similarity": s_sim,
                    "feedback_adjustment": feedback_adjustment,
                    "feedback_total": feedback_total,
                    "confidence_score": score_total,
                }
            )

        out.sort(key=lambda x: float(x.get("confidence_score") or 0.0), reverse=True)
        return out
    except Exception as exc:
        _log.warning("confidence_score 계산 예외: %s", exc, exc_info=True)
        return []



def cohort_stat_rows_to_top_rx_lines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """집계 결과를 prescription 프롬프트의 top_rx 행 형태로 변환한다."""
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        pc = r.get("prescription_code")
        pn = r.get("canonical_name") or ""
        out.append(
            {
                "내원번호": "cohort_frequency",
                "처방시퀀스": i + 1,
                "처방코드": pc,
                "처방명": pn,
                "prescription_code": pc,
                "canonical_name": pn,
                "source": "diagnosis_cohort_frequency",
                "cohort_prescription_count": r.get("cohort_prescription_count"),
            }
        )
    return out


def format_cohort_similar_outcomes_summary(
    disease_codes: list[str],
    stats: list[dict[str, Any]],
    *,
    max_lines: int = 25,
) -> str:
    """similar_outcomes 블록에 넣을 한국어 요약 문자열."""
    if not stats:
        return ""
    codes = [str(c).strip() for c in disease_codes if c and str(c).strip()]
    head = (
        f"[Arango 그래프 집계] 상병 {', '.join(codes)} 에 연결된 방문들에서 "
        f"관찰된 처방 라인 빈도 상위 {min(len(stats), max_lines)}건 (코호트 참고, 실제 처방 결정은 임상 판단):"
    )
    lines = [head]
    for i, r in enumerate(stats[:max_lines], 1):
        pc = r.get("prescription_code")
        pn = r.get("canonical_name")
        cnt = r.get("cohort_prescription_count")
        lines.append(f"  {i}. {pn} (코드 {pc}) — 처방 라인 수 약 {cnt}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="처방 추천 프롬프트 → Gemini → JSON (컨텍스트는 JSON 파일).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            run_graph_qa.py -q "…" 는 그래프에 대해 질문 → 모델이 AQL을 직접 짭니다.
            이 스크립트는 -f 로 넣은 환자·그래프 요약을 프롬프트에 싣고, -q 는 그 위에 덧붙는
            임상 질문(선택)입니다. 기본은 Arango를 호출하지 않습니다.

            예시:
              %(prog)s -f patient_ctx.example.json
              %(prog)s -f patient_ctx.example.json --fetch-top-rx-from-arango
              %(prog)s -f patient_ctx.example.json -q "소염진통제 대안을 우선해 주세요"
            """
        ).strip(),
    )
    p.add_argument(
        "-f",
        "--context",
        type=Path,
        default=SCRIPT_DIR / "patient_ctx.example.json",
        help="patient_id, symptoms, history, top_rx, similar_outcomes 가 있는 JSON",
    )
    p.add_argument(
        "-q",
        "--query",
        default="",
        help="Clinician question (선택). 비우면 프롬프트 기본 지시만 사용.",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        help="Gemini 모델 ID (기본: GEMINI_MODEL 또는 gemini-2.5-flash-lite)",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="샘플링 온도 (0 권장)",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="모델 원문만 출력 (JSON 파싱·검증 생략)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="설정 요약 출력 생략",
    )
    p.add_argument(
        "--fetch-top-rx-from-arango",
        action="store_true",
        help=(
            "patient_id 로 visits 를 찾아 visit_has_order → order_lines 조회 결과로 "
            "JSON의 top_rx 를 덮어씀 (run_graph_qa 와 동일 Arango 연결 설정)"
        ),
    )
    p.add_argument(
        "--arango-top-rx-limit",
        type=int,
        default=80,
        metavar="N",
        help="--fetch-top-rx-from-arango 시 최대 처방 행 수 (기본 80)",
    )
    return p.parse_args()


def main() -> None:
    _load_dotenv_if_present()
    args = parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        print(
            "[오류] GOOGLE_API_KEY 가 설정되지 않았습니다. export 하거나 .env 에 넣어 주세요.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    ctx_path = args.context.resolve()
    if not ctx_path.is_file():
        print(f"[오류] 컨텍스트 파일이 없습니다: {ctx_path}", file=sys.stderr)
        raise SystemExit(2)

    ctx = load_prescription_context_file(ctx_path)

    if args.fetch_top_rx_from_arango:
        rows = fetch_top_rx_from_arango(ctx["patient_id"], limit=args.arango_top_rx_limit)
        if rows:
            ctx["top_rx"] = rows
            if not args.quiet:
                print(
                    f"[Arango] top_rx {len(rows)}건 로드 (patient_id={ctx['patient_id']!r})",
                    file=sys.stderr,
                )
        else:
            print(
                "[경고] Arango에서 해당 patient_id 방문·처방 라인을 찾지 못했습니다. "
                "JSON 파일의 top_rx 를 그대로 사용합니다.",
                file=sys.stderr,
            )

    cq = (args.query or "").strip() or None
    user_msg = build_prescription_agent_prompt(
        patient_id=ctx["patient_id"],
        symptoms=ctx["symptoms"],
        history=ctx["history"],
        top_rx=ctx["top_rx"],
        similar_outcomes=ctx["similar_outcomes"],
        clinician_question=cq,
        mention_links=ctx.get("mention_links"),
    )

    if not args.quiet:
        print(
            textwrap.dedent(
                f"""
                --- 설정 요약 ---
                Context: {ctx_path}
                Gemini: {args.model}  temperature={args.temperature}
                Clinician -q: {cq or "(없음)"}
                Arango top_rx: {"예 (--fetch-top-rx-from-arango)" if args.fetch_top_rx_from_arango else "아니오 (JSON만)"}
                """
            ).strip()
        )

    llm = ChatGoogleGenerativeAI(model=args.model, temperature=args.temperature)
    try:
        resp = llm.invoke(
            [
                ("system", SYSTEM_PRESCRIPTION),
                ("human", user_msg),
            ]
        )
    except ChatGoogleGenerativeAIError as e:
        print(f"[오류] Gemini 호출 실패: {e}", file=sys.stderr)
        raise SystemExit(3) from e

    raw = (resp.content or "").strip() if hasattr(resp, "content") else str(resp).strip()

    if args.raw:
        print(raw)
        return

    try:
        data = parse_prescriptions_llm_response(raw)
    except ValueError as e:
        print(f"[오류] JSON 파싱/검증 실패: {e}", file=sys.stderr)
        print("--- 모델 원문 ---", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(4) from e

    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
