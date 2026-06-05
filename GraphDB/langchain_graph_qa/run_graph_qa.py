#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ArangoDB 그래프 자연어 질의 (NL → AQL → 답변) — Google Gemini 전용
================================================================================

【목적】
  상병·처방 정규화 데이터가 적재된 ArangoDB에 대해, 자연어 질문을 받아
  LangChain ``ArangoGraphQAChain``이 AQL을 생성·실행한 뒤, 결과를 **한국어**로 요약합니다.

【전제】
  - ``GraphDB/data_normalize/import_to_arango.py`` 등으로 다음 컬렉션이 채워져 있어야 합니다.
      문서: visits, diagnoses, prescription_masters, order_lines, special_notes, note_mentions
      엣지: visit_has_diagnosis, visit_has_order, order_refers_prescription,
            visit_has_note, order_associated_diagnosis, note_has_mention,
            diagnosis_has_mention, prescription_has_mention (특이사항·mention 직접 연결, CSV 재생성·재적재 후)
      (선택) note_mentions.embedding — ``embed_note_mentions.py`` 로 채우면 의미 유사 검색 가능
      (향후) 질의 임베딩 기반 vector retrieval 은 QA 측에 별도 연동 — 6단계 예정
  - Google API 키: 환경 변수 ``GOOGLE_API_KEY`` 또는 이 스크립트와 같은 디렉터리의 ``.env``
  - Arango 연결: ``Back-End/src/main/resources/application-local.properties`` 의 ``arangodb.*``
    (또는 ``ARANGO_HOST``, ``ARANGO_PORT``, ``ARANGO_USER``, ``ARANGO_PASSWORD``, ``ARANGO_DATABASE``)

【보안】
  LLM이 생성한 AQL은 읽기 외 동작을 시도할 수 있습니다. 운영 DB·고권한 계정에는 연결하지 마세요.

【설치】
  Python 3.10+ 가상환경 권장(langchain-google-genai 최신이 3.10 이상 요구하는 경우가 많음).
  cd GraphDB/langchain_graph_qa
  python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
  pip install -U pip
  pip install -r requirements.txt
  # 의존성은 가상환경에 한 번만 설치하면 됩니다. 실행할 때마다 pip install 할 필요 없음.

【실행 예】
  python run_graph_qa.py
  python run_graph_qa.py -q "E11 진단이 연결된 방문은 몇 건인가요?"
  python run_graph_qa.py -q "처방 상위 5개 코드를 알려주세요" --show-aql
  python run_graph_qa.py --quiet
================================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Literal

# langchain-google-genai 는 PyPI 기준 Python 3.9+ 만 지원 (3.8 venv 에서는 pip 도 실패함).
if sys.version_info < (3, 9):
    print(
        textwrap.dedent(
            f"""
            [오류] 현재 Python {sys.version_info.major}.{sys.version_info.minor} 입니다.
            Gemini 연동 패키지(langchain-google-genai)는 3.9 이상만 지원합니다. 3.10 이상을 권장합니다.

            예: 프로젝트 루트에서 3.11 로 가상환경 다시 만들기
              cd /path/to/PatboongIsBetterthanSyuboong
              rm -rf .venv
              python3.11 -m venv .venv
              source .venv/bin/activate
              pip install -U pip
              pip install -r GraphDB/langchain_graph_qa/requirements.txt
            """
        ).strip(),
        file=sys.stderr,
    )
    raise SystemExit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from arango import ArangoClient
from arango.exceptions import ArangoError

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from langchain_community.chains.graph_qa.arangodb import ArangoGraphQAChain
from langchain_community.chains.graph_qa.prompts import (
    AQL_FIX_PROMPT,
    AQL_GENERATION_PROMPT,
    AQL_QA_PROMPT,
)
from langchain_community.graphs.arangodb_graph import ArangoGraph
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from lc_arango_chain import build_arango_graph_qa_chain

REPO_ROOT = SCRIPT_DIR.parent.parent
SPRING_LOCAL = (
    REPO_ROOT / "Back-End" / "src" / "main" / "resources" / "application-local.properties"
)

# ---------------------------------------------------------------------------
# 스키마 힌트 (LLM few-shot; 실제 스키마는 ArangoGraph가 조회)
# ---------------------------------------------------------------------------

AQL_EXAMPLES = textwrap.dedent(
    """
    -- [필수 규칙 1] 문서 **속성 접근**: 한글·혼합 필드명은 백틱: alias.`속성명`
    --   visits: `내원번호_norm` / diagnoses: `상병코드_norm` / order_lines: `처방코드_norm` 등
    -- [필수 규칙 2] RETURN { ... } **객체의 키**가 한글이면 bare 키(처방코드:) 불가 → 반드시 따옴표 키:
    --   "처방코드": ol.`처방코드_norm`   (오류: 처방코드: ol.`처방코드_norm`)
    -- COLLECT / FILTER 등에서도 속성 접근은 백틱, 객체 리터럴 키는 따옴표

    -- 방문(visit) 문서 개수
    RETURN LENGTH(FOR d IN visits RETURN 1)

    -- visits: 한글 속성 조회 예
    FOR v IN visits
      LIMIT 5
      RETURN { visit_id: v.visit_id, "내원번호": v.`내원번호_norm` }

    -- 특정 내원번호에 이미 기록된 처방 라인 나열 ("추천" 질문도 이런 조회로 해석)
    WITH visits, visit_has_order, order_lines
    FOR v IN visits
      FILTER v.`내원번호_norm` == "530524451"
      FOR e IN visit_has_order
        FILTER e._from == v._id
        LET ol = DOCUMENT(e._to)
        RETURN {
          visit_id: v.visit_id,
          order_line_id: ol.order_line_id,
          "처방코드": ol.`처방코드_norm`,
          "처방명": ol.`처방명_norm`
        }

    -- 동일 내원: 처방·상병을 한 번에 (중첩 RETURN 도 한글 키는 따옴표)
    WITH visits, visit_has_order, order_lines, visit_has_diagnosis, visit_has_note, special_notes
    FOR v IN visits
      FILTER v.`내원번호_norm` == "530524451"
      LET orders = (
        FOR e IN visit_has_order
          FILTER e._from == v._id
          LET ol = DOCUMENT(e._to)
          RETURN {
            order_line_id: ol.order_line_id,
            "처방코드": ol.`처방코드_norm`,
            "처방명": ol.`처방명_norm`
          }
      )
      RETURN {
        visit_id: v.visit_id,
        orders: orders,
        "상병코드목록": (
          FOR e IN visit_has_diagnosis
            FILTER e._from == v._id
            RETURN DOCUMENT(e._to).`상병코드_norm`
        ),
        "특이사항목록": (
          FOR e IN visit_has_note
            FILTER e._from == v._id
            RETURN DOCUMENT(e._to).`특이사항_norm`
        )
      }

    -- diagnoses: 상병 마스터에서 한글 코드 필드
    FOR d IN diagnoses
      LIMIT 5
      RETURN { diagnosis_code: d.diagnosis_code, "상병코드": d.`상병코드_norm` }

    -- 상병 diagnoses/E11 과 연결된 방문 _key 일부
    FOR e IN visit_has_diagnosis
      FILTER e._to == "diagnoses/E11"
      LIMIT 10
      RETURN SPLIT(e._from, "/")[1]

    -- 상병 diagnoses/E11 과 연결된 **서로 다른 방문** 개수
    -- (ArangoDB에는 COLLECT DISTINCT 가 없음. COLLECT 만으로 그룹이 유일해짐)
    RETURN LENGTH(
      FOR e IN visit_has_diagnosis
        FILTER e._to == "diagnoses/E11"
        COLLECT visitRef = e._from
        RETURN visitRef
    )

    -- COLLECT 에서 한글 속성 (백틱 필수): 진단 노드별 연결 수
    FOR e IN visit_has_diagnosis
      COLLECT diag = e._to WITH COUNT INTO c
      SORT c DESC
      LIMIT 10
      RETURN { diagnosis_vertex: diag, visit_edges: c }

    -- order_lines: 특정 처방코드와 연결된 상병 코드 나열 (엣지 order_associated_diagnosis)
    FOR ol IN order_lines
      FILTER ol.`처방코드_norm` == "652100200"
      FOR e IN order_associated_diagnosis
        FILTER e._from == ol._id
        RETURN DISTINCT SPLIT(e._to, "/")[1]

    -- diagnoses: COLLECT 에서 한글 필드로 그룹 (백틱 필수)
    FOR d IN diagnoses
      COLLECT sc = d.`상병코드_norm` WITH COUNT INTO n
      RETURN { "상병코드": sc, "문서수": n }

    -- order_lines: 처방명_norm 이 있는 라인 (키워드 검색)
    FOR ol IN order_lines
      FILTER CONTAINS(LOWER(ol.`처방명_norm`), "glucose")
      LIMIT 10
      RETURN {
        order_line_id: ol.order_line_id,
        "처방명": ol.`처방명_norm`,
        "처방코드": ol.`처방코드_norm`
      }

    -- 처방 마스터로 묶인 엣지 수 상위 5개
    FOR e IN order_refers_prescription
      COLLECT to_key = e._to WITH COUNT INTO c
      SORT c DESC
      LIMIT 5
      RETURN { prescription: to_key, count: c }

    -- 특이사항 텍스트에 키워드 포함 (증상·메모 검색)
    FOR n IN special_notes
      FILTER CONTAINS(LOWER(n.`특이사항_norm`), "피로")
         OR CONTAINS(LOWER(n.`특이사항_norm`), "근육")
      LIMIT 20
      RETURN { visit_id: n.visit_id, note_id: n._key, text: n.`특이사항_norm` }

    -- ========== 특이사항 반드시 “경유 탐색” (직접 special_notes 만 보지 말 것) ==========
    -- [상병 → 방문 → 특이사항] (버그 수정: note 문서는 visit_has_note 엣지의 e2._to)
    -- LIMIT 는 서브쿼리 밖에서 최종 행만 제한
    WITH diagnoses, visit_has_diagnosis, visits, visit_has_note, special_notes
    LET _dx_note_rows = (
      FOR d IN diagnoses
        FILTER d._key == "E11" OR d.`상병코드_norm` == "E11"
        FOR e IN visit_has_diagnosis
          FILTER e._to == d._id
          LET v = DOCUMENT(e._from)
          FOR e2 IN visit_has_note
            FILTER e2._from == v._id
            LET n = DOCUMENT(e2._to)
            RETURN { visit_id: v.visit_id, "특이사항": n.`특이사항_norm`, note_id: n._key }
    )
    FOR r IN _dx_note_rows
      LIMIT 20
      RETURN r

    -- [상병 → mention 직접] diagnosis_has_mention (적재 시 특이사항 회수 안정화)
    WITH diagnoses, diagnosis_has_mention, note_mentions
    FOR d IN diagnoses
      FILTER d._key == "E11" OR d.`상병코드_norm` == "E11"
      FOR e IN diagnosis_has_mention
        FILTER e._from == d._id
        LET m = DOCUMENT(e._to)
        LIMIT 20
        RETURN {
          visit_id: m.visit_id,
          mention_id: m.mention_id,
          mention_type: m.mention_type,
          fragment: m.text,
          link_source: e.link_source,
          confidence: e.confidence
        }

    -- [처방마스터 → 오더라인 → 방문 → 특이사항] 처방·검사 질문 시 동일
    WITH prescription_masters, order_refers_prescription, order_lines, visits, visit_has_note, special_notes
    LET _rx_note_rows = (
      FOR pm IN prescription_masters
        FILTER pm._key == "652100200" OR pm.prescription_code == "652100200"
        FOR e IN order_refers_prescription
          FILTER e._to == pm._id
          LET ol = DOCUMENT(e._from)
          LET v = DOCUMENT(CONCAT("visits/", ol.visit_id))
          FOR e2 IN visit_has_note
            FILTER e2._from == v._id
            LET n = DOCUMENT(e2._to)
            RETURN { visit_id: v.visit_id, "특이사항": n.`특이사항_norm`, order_line_id: ol.order_line_id }
    )
    FOR r IN _rx_note_rows
      LIMIT 20
      RETURN r

    -- [처방 → mention 직접] prescription_has_mention
    WITH prescription_masters, prescription_has_mention, note_mentions
    FOR pm IN prescription_masters
      FILTER pm._key == "652100200" OR pm.prescription_code == "652100200"
      FOR e IN prescription_has_mention
        FILTER e._from == pm._id
        LET m = DOCUMENT(e._to)
        LIMIT 20
        RETURN {
          visit_id: m.visit_id,
          mention_id: m.mention_id,
          fragment: m.text,
          mention_type: m.mention_type,
          link_source: e.link_source
        }

    -- [내원번호(환자 단위 프록시) → 방문 → 특이사항] 원내 환자키가 없으면 내원번호로 동일 경로
    WITH visits, visit_has_note, special_notes
    FOR v IN visits
      FILTER v.`내원번호_norm` == "530524451"
      FOR e IN visit_has_note
        FILTER e._from == v._id
        RETURN DOCUMENT(e._to).`특이사항_norm`

    -- [note_mentions 조각 검색] 문장/개념 단위 + 부모 노트 연결 (visit_id 는 비정규화 필드)
    WITH note_mentions, note_has_mention, special_notes
    FOR m IN note_mentions
      FILTER m.mention_type == "LAB"
         OR CONTAINS(LOWER(m.text), "hb")
      LIMIT 25
      LET n = FIRST(
        FOR e IN note_has_mention
          FILTER e._to == m._id
          RETURN DOCUMENT(e._from)
      )
      RETURN { mention_type: m.mention_type, fragment: m.text, visit_id: m.visit_id, parent_note: n.`특이사항_norm` }

    -- [임베딩 유사도] note_mentions.embedding 필드가 있고 ArangoDB 가 COSINE_SIMILARITY 를 지원하면
    --   FOR m IN note_mentions FILTER m.embedding != null
    --   LET s = COSINE_SIMILARITY(m.embedding, @qvec) ... 형태로 검색. 미지원·미적재 시 m.text 로 CONTAINS.
    """
).strip()


# ---------------------------------------------------------------------------
# 한국어 응답·한국어 질의 대응 프롬프트 (공식 템플릿 확장)
# ---------------------------------------------------------------------------
# 접미사는 LangChain PromptTemplate 에 합쳐짐. {…} 문자는 변수로 오인될 수 있어 접미사에는 쓰지 않음.

_AQL_GEN_KO_SUFFIX = textwrap.dedent(
    """

    [언어] User Input은 한국어일 수 있습니다. 의도를 파악하여 올바른 AQL만 생성하세요.
    출력은 여전히 AQL 코드 블록(백틱 3개) 안의 쿼리만 포함해야 합니다.

    [업무 범위 — 기본 프롬프트의 '거절' 규칙보다 우선]
    이 도구는 임상 의학적 '진단·처방 결정'을 하지 않습니다. 대신 그래프 DB에 **이미 저장된**
    방문·처방 라인·상병·특이사항을 **읽기 전용 AQL**로 조회합니다.
    - 사용자가 "처방 추천", "적절한 처방", "뭐가 좋을까"처럼 표현해도 → **해당 내원에 실제로 기록된**
      처방(order_lines, prescription_masters)과 상병·특이사항을 나열·집계하는 AQL로 해석합니다.
    - **절대** "I cannot help", "도와줄 수 없습니다" 등 **거절 문장만** 내지 마세요. (파이프라인이 즉시 실패합니다)
    - 항상 **WITH** 로 필요한 컬렉션을 열고, **삭제·수정·INSERT 없이** FOR/FILTER/RETURN 만 사용합니다.

    [내원번호가 나오면]
    visits.visit_id 는 보통 문자열 VISIT_ 와 내원번호를 이어 붙인 값(예: VISIT_530524451)이거나,
    v.`내원번호_norm` == "숫자" 로 같은 방문을 찾습니다.

    [ArangoDB 한글 속성명 — 필수]
    스키마에 한글 또는 한글+영문 혼합 필드가 있으면, AQL에서 절대 bare identifier 로 쓰지 말고
    반드시 백틱으로 감싸세요: doc.`상병코드_norm`, ol.`처방코드_norm`, ol.`처방명_norm`, n.`특이사항_norm`, v.`내원번호_norm`, ol.`처방시퀀스_norm`
    COLLECT, AGGREGATE, SORT, FILTER, RETURN 어디에서든 동일합니다. (미준수 시 syntax error 발생)

    [RETURN 객체 리터럴의 키 — 필수]
    RETURN 블록 안에서 한글 키 이름을 쓸 때는 처방코드: 처럼 **bare 키를 쓰면 문법 오류**입니다.
    반드시 따옴표로 감싼 키를 쓰세요. 예: "처방코드": ol.`처방코드_norm`, "처방명": ol.`처방명_norm`, "상병코드": d.`상병코드_norm`
    출력 AQL 첫 줄은 WITH 또는 FOR 만 가능합니다. json 이나 설명 문구를 쿼리 앞에 붙이지 마세요.

    [AQL COLLECT]
    ArangoDB 에는 SQL 의 "COLLECT DISTINCT" / "SELECT DISTINCT" 같은 키워드 조합이 없습니다.
    유일 값 개수는 FOR 안에서 COLLECT 컬럼 = 식 만 쓰고, 바깥에서 RETURN LENGTH(서브쿼리) 로 세세요.

    [특이사항·메모 검색 — 반드시 다중 홉]
    특이사항(special_notes)은 방문(visits)에만 연결되어 있습니다. 질문에 상병·처방·내원이 섞이면
    **단순히 special_notes 만 FOR 하지 말고** 아래 중 하나로 반드시 경유하세요.
    - 상병 관련: diagnoses → visit_has_diagnosis → visits → visit_has_note → special_notes
    - 처방·검사 관련: prescription_masters → order_refers_prescription → order_lines → (visit_id 로 visits) → visit_has_note → special_notes
    - 환자·내원 관련: visits FILTER 내원번호_norm → visit_has_note → special_notes
    조각 단위 검색은 note_mentions 컬렉션(note_has_mention 으로 special_notes 와 연결)을 사용할 수 있습니다.
    상병·처방과 mention 을 짧게 잇는 엣지(diagnosis_has_mention, prescription_has_mention)가 있으면
    특이사항 질의 시 FOR IN diagnosis_has_mention / prescription_has_mention 을 우선 고려하세요.
    embedding 필드가 없으면 COSINE_SIMILARITY 쿼리는 쓰지 말고 m.text / 특이사항_norm 에 CONTAINS·LIKE 를 쓰세요.
    """
)

_AQL_QA_KO_SUFFIX = textwrap.dedent(
    """

    [출력 언어 — 필수]
    - 최종 Summary(답변 본문)는 **반드시 한국어**로 작성합니다.
    - **합니다체** 등 정중한 문체를 사용합니다.
    - 사용자가 AQL·쿼리 작성법을 묻지 않는 한, SQL/AQL/JSON 같은 구현 세부를 굳이 언급하지 않습니다.
    - 숫자·코드(E11, visit_id 등)는 그대로 인용해도 됩니다.
    - 결과가 비었거나 질문과 데이터가 맞지 않으면, 한국어로 그 사실을 명확히 알립니다.
    """
)


def _prompt_with_suffix(base: PromptTemplate, suffix: str) -> PromptTemplate:
    """기존 LangChain PromptTemplate 뒤에 지시문을 덧붙인 복제본을 만듭니다."""
    variables = list(base.input_variables)
    return PromptTemplate(input_variables=variables, template=base.template + suffix)


def build_korean_prompts() -> tuple[PromptTemplate, PromptTemplate, PromptTemplate]:
    """
    AQL 생성·수정·최종 요약 단계용 프롬프트를 반환합니다.

    Returns:
        (aql_generation_prompt, aql_fix_prompt, qa_prompt)
        qa_prompt는 한국어 답변, gen/fix 접미사는 한글 속성 백틱 규칙을 강조합니다.
    """
    gen = _prompt_with_suffix(AQL_GENERATION_PROMPT, _AQL_GEN_KO_SUFFIX)
    _fix_suffix = textwrap.dedent(
        """

        [수정 시 유의]
        - 문서 속성 접근: 한글 필드는 백틱 (`처방코드_norm` 등).
        - RETURN 객체 안의 한글 **키**는 bare 가 아니라 따옴표: "처방코드": ol.`처방코드_norm`
        - 응답은 순수 AQL만 (앞에 json, 마크다운, 설명 붙이지 않음).
        """
    )
    fix = _prompt_with_suffix(AQL_FIX_PROMPT, _fix_suffix)
    qa = _prompt_with_suffix(AQL_QA_PROMPT, _AQL_QA_KO_SUFFIX)
    return gen, fix, qa


# ---------------------------------------------------------------------------
# 설정 로드
# ---------------------------------------------------------------------------


def _parse_spring_properties(path: Path) -> dict[str, str]:
    """Java ``application*.properties`` 형식(키=값)을 단순 파싱합니다."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def load_arango_config() -> dict[str, str | int]:
    """
    Arango 접속 정보를 환경 변수 → Spring 로컬 프로퍼티 → 기본값 순으로 읽습니다.

    Returns:
        host, port, user, password, database 키를 가진 dict.
    """
    props = _parse_spring_properties(SPRING_LOCAL)
    hosts = os.environ.get("ARANGO_HOSTS") or props.get("arangodb.hosts", "127.0.0.1:8529")
    if ":" in hosts:
        host, port_s = hosts.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = hosts, 8529
    host = os.environ.get("ARANGO_HOST", host)
    port = int(os.environ.get("ARANGO_PORT", str(port)))
    return {
        "host": host,
        "port": port,
        "user": os.environ.get("ARANGO_USER", props.get("arangodb.user", "root")),
        "password": os.environ.get("ARANGO_PASSWORD", props.get("arangodb.password", "")),
        "database": os.environ.get(
            "ARANGO_DATABASE", props.get("arangodb.database", "bitcomputer_graph")
        ),
    }


def _load_dotenv_if_present() -> None:
    """``langchain_graph_qa/.env`` 가 있으면 로드합니다."""
    if not load_dotenv:
        return
    env_file = SCRIPT_DIR / ".env"
    if env_file.is_file():
        load_dotenv(env_file)


def connect_arango(cfg: dict[str, str | int]) -> Any:
    """
    ArangoDB에 연결해 데이터베이스 핸들을 반환합니다.

    Raises:
        SystemExit: 연결·인증 실패 시.
    """
    url = f"http://{cfg['host']}:{cfg['port']}"
    client = ArangoClient(hosts=url)
    try:
        db = client.db(
            str(cfg["database"]),
            username=str(cfg["user"]),
            password=str(cfg["password"]),
        )
        db.properties()
    except ArangoError as e:
        print(f"[오류] ArangoDB 연결 실패 ({url}, DB={cfg['database']}): {e}", file=sys.stderr)
        raise SystemExit(2) from e
    return db


def detect_query_mode(query: str) -> Literal["diagnosis_note", "prescription_note", "generic"]:
    """특이사항·상병·처방이 섞인 질문을 단순 휴리스틱으로 분류 (LLM 아님)."""
    import re as _re

    note_kw = ("특이사항", "메모", "병력", "소견", "관련 note", "노트")
    has_note = any(k in query for k in note_kw)
    if _re.search(r"\b[A-Z]\d{2}(?:\.\d+)?\b", query.upper()) and (
        has_note or "상병" in query or "진단" in query or "질환" in query
    ):
        return "diagnosis_note"
    if _re.search(r"\b\d{6,}\b", query) and (
        has_note or "처방" in query or "검사" in query or "약" in query
    ):
        return "prescription_note"
    return "generic"


def _aql_rows(db: Any, aql: str, bind_vars: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        cur = db.aql.execute(aql, bind_vars=bind_vars or {})
        return [dict(x) for x in cur]
    except ArangoError:
        return []


def run_diagnosis_note_query(db: Any, user_query: str) -> list[dict[str, Any]]:
    """diagnosis_has_mention 우선, 없으면 Diagnosis→Visit→Note→Mention 경로."""
    import re as _re

    m = _re.search(r"\b([A-Z]\d{2}(?:\.\d+)?)\b", user_query.upper())
    if not m:
        return []
    code = m.group(1)
    aql_direct = """
    WITH diagnoses, diagnosis_has_mention, note_mentions
    FOR d IN diagnoses
      FILTER d._key == @code OR d.diagnosis_code == @code
      FOR e IN diagnosis_has_mention
        FILTER e._from == d._id
        LET m = DOCUMENT(e._to)
        RETURN {
          path: "diagnosis_has_mention",
          visit_id: m.visit_id,
          mention_id: m.mention_id,
          mention_type: m.mention_type,
          fragment: m.text,
          link_source: e.link_source,
          confidence: e.confidence,
          review_flag: e.review_flag
        }
    LIMIT 80
    """
    rows = _aql_rows(db, aql_direct, {"code": code})
    if rows:
        return rows
    aql_fb = """
    WITH diagnoses, visit_has_diagnosis, visits, visit_has_note, special_notes, note_mentions, note_has_mention
    FOR d IN diagnoses
      FILTER d._key == @code OR d.diagnosis_code == @code
      FOR ev IN visit_has_diagnosis
        FILTER ev._to == d._id
        LET v = DOCUMENT(ev._from)
        FOR e2 IN visit_has_note
          FILTER e2._from == v._id
          LET n = DOCUMENT(e2._to)
          FOR em IN note_has_mention
            FILTER em._from == n._id
            LET m = DOCUMENT(em._to)
            RETURN {
              path: "via_visit_note_mention",
              visit_id: v.visit_id,
              mention_id: m.mention_id,
              fragment: m.text,
              mention_type: m.mention_type,
              parent_note: n.`특이사항_norm`
            }
    LIMIT 80
    """
    return _aql_rows(db, aql_fb, {"code": code})


def run_prescription_note_query(db: Any, user_query: str) -> list[dict[str, Any]]:
    """prescription_has_mention 우선, 없으면 Prescription→Order→Visit→Note→Mention."""
    import re as _re

    m = _re.search(r"\b(\d{6,})\b", user_query)
    if not m:
        return []
    code = m.group(1)
    aql_direct = """
    WITH prescription_masters, prescription_has_mention, note_mentions
    FOR pm IN prescription_masters
      FILTER pm._key == @code OR pm.prescription_code == @code
      FOR e IN prescription_has_mention
        FILTER e._from == pm._id
        LET m = DOCUMENT(e._to)
        RETURN {
          path: "prescription_has_mention",
          visit_id: m.visit_id,
          mention_id: m.mention_id,
          mention_type: m.mention_type,
          fragment: m.text,
          link_source: e.link_source,
          confidence: e.confidence
        }
    LIMIT 80
    """
    rows = _aql_rows(db, aql_direct, {"code": code})
    if rows:
        return rows
    aql_fb = """
    WITH prescription_masters, order_refers_prescription, order_lines, visits, visit_has_note, special_notes,
         note_mentions, note_has_mention
    FOR pm IN prescription_masters
      FILTER pm._key == @code OR pm.prescription_code == @code
      FOR er IN order_refers_prescription
        FILTER er._to == pm._id
        LET ol = DOCUMENT(er._from)
        LET v = DOCUMENT(CONCAT("visits/", ol.visit_id))
        FOR e2 IN visit_has_note
          FILTER e2._from == v._id
          LET n = DOCUMENT(e2._to)
          FOR em IN note_has_mention
            FILTER em._from == n._id
            LET m = DOCUMENT(em._to)
            RETURN {
              path: "via_order_visit_note_mention",
              visit_id: v.visit_id,
              order_line_id: ol.order_line_id,
              mention_id: m.mention_id,
              fragment: m.text,
              mention_type: m.mention_type,
              parent_note: n.`특이사항_norm`
            }
    LIMIT 80
    """
    return _aql_rows(db, aql_fb, {"code": code})


def format_direct_rows(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    """CLI 인자를 정의하고 파싱합니다."""
    p = argparse.ArgumentParser(
        description="Arango 의료 그래프에 대해 자연어 질의 → 한국어 답변 (Gemini).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            예시:
              %(prog)s -q "진단 코드 종류는 몇 가지인가요?"
              %(prog)s -q "방문 수" --show-aql --top-k 20
            """
        ).strip(),
    )
    p.add_argument(
        "-q",
        "--query",
        default="데이터베이스에 기록된 서로 다른 상병 코드는 몇 종류이며, 각 코드를 알려주세요.",
        help="한국어 자연어 질문",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        help=(
            "Gemini 모델 ID (기본: GEMINI_MODEL 또는 gemini-2.5-flash-lite). "
            "무료 등급은 모델별 일일 한도가 매우 낮고, 이 체인은 질의 1회당 LLM을 여러 번 호출합니다. "
            "429 가 나면 --model gemini-2.5-flash 등 다른 모델이나 결제/한도 상향을 검토하세요."
        ),
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="샘플링 온도 (0 권장)",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=10,
        metavar="K",
        help="AQL 결과를 요약에 넘기는 최대 행 수 (체인의 top_k)",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=3,
        metavar="N",
        help="AQL 실행 실패 시 재생성 최대 횟수",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="체인 verbose 로그 끄기",
    )
    p.add_argument(
        "--show-aql",
        action="store_true",
        help="실행에 사용된 AQL을 표준 출력에 추가",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="답변과 옵션 필드를 JSON 한 줄로 출력 (--show-aql 과 함께 쓰기 좋음)",
    )
    p.add_argument(
        "--force-chain",
        action="store_true",
        help="직접 AQL 라우팅 없이 항상 ArangoGraphQAChain 만 사용 (generic LLM 경로)",
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

    cfg = load_arango_config()
    db = connect_arango(cfg)

    if not args.quiet:
        print(
            textwrap.dedent(
                f"""
                --- 설정 요약 ---
                Arango: http://{cfg['host']}:{cfg['port']}  DB={cfg['database']}  user={cfg['user']}
                Gemini: {args.model}  temperature={args.temperature}  top_k={args.top_k}
                """
            ).strip()
        )

    graph = ArangoGraph(db)
    aql_gen_prompt, aql_fix_prompt, qa_prompt_ko = build_korean_prompts()

    llm = ChatGoogleGenerativeAI(
        model=args.model,
        temperature=args.temperature,
    )

    chain = build_arango_graph_qa_chain(
        ArangoGraphQAChain,
        llm,
        graph=graph,
        verbose=not args.quiet,
        aql_examples=AQL_EXAMPLES,
        aql_generation_prompt=aql_gen_prompt,
        aql_fix_prompt=aql_fix_prompt,
        qa_prompt=qa_prompt_ko,
        top_k=args.top_k,
        max_aql_generation_attempts=args.max_retries,
        return_aql_query=args.show_aql or args.json,
    )

    mode = detect_query_mode(args.query)
    direct_rows: list[dict[str, Any]] = []
    if not args.force_chain:
        if mode == "diagnosis_note":
            direct_rows = run_diagnosis_note_query(db, args.query)
        elif mode == "prescription_note":
            direct_rows = run_prescription_note_query(db, args.query)

    if direct_rows:
        result_text = format_direct_rows(direct_rows)
        if args.json:
            payload: dict[str, Any] = {
                "answer": result_text,
                "query": args.query,
                "routing": "direct_aql",
                "query_mode": mode,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print()
            print("=== 답변 (직접 AQL, mention 우선 경로) ===")
            print(result_text)
        if not args.quiet:
            print(
                f"\n[라우팅] mode={mode} rows={len(direct_rows)} (LLM 체인 생략)",
                file=sys.stderr,
            )
        return

    try:
        out = chain.invoke({"query": args.query})
    except ChatGoogleGenerativeAIError as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(
                textwrap.dedent(
                    """
                    [오류] Gemini API 할당량(429 RESOURCE_EXHAUSTED)에 걸렸습니다. 코드나 Arango 문제가 아닙니다.

                    - 무료 플랜은 모델마다 일일(또는 분당) generate 요청 한도가 작습니다. 메시지에 나온 한도를 확인하세요.
                    - ArangoGraphQAChain 은 AQL 생성·수정·한국어 요약 등으로 질문 한 번에 API를 여러 번 호출합니다. 그래서 체감상 금방 한도에 닿을 수 있습니다.

                    대응:
                      • 잠시 후(분당 제한이면 수십 초~분) 다시 시도하거나, 다음 날(일일 한도면) 다시 시도
                      • Google AI Studio / Cloud 에서 결제·플랜으로 한도 상향: https://ai.google.dev/gemini-api/docs/rate-limits
                      • 다른 모델로 쿼터를 나눠 쓰기: 예) python run_graph_qa.py --model gemini-2.5-flash -q "..."
                    """
                ).strip(),
                file=sys.stderr,
            )
            print(f"\n[원본 메시지]\n{err}", file=sys.stderr)
            raise SystemExit(3) from e
        raise

    result_text = out.get("result", "")
    aql_text = out.get("aql_query", "")

    if args.json:
        payload = {"answer": result_text, "query": args.query}
        if args.show_aql or aql_text:
            payload["aql"] = aql_text
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print()
        print("=== 답변 ===")
        print(result_text)
        if args.show_aql and aql_text:
            print()
            print("=== 실행된 AQL ===")
            print(aql_text.strip())


if __name__ == "__main__":
    main()
