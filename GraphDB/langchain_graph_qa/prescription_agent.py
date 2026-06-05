# -*- coding: utf-8 -*-
"""
의료 그래프 기반 처방 추천 에이전트용 사용자 메시지 프롬프트.

Spring Boot 등에서 동일 본문을 쓸 때는 {patient_id}, {symptoms} 등 템플릿 변수로 치환하면 됩니다.
이 모듈에서는 예시 JSON의 중괄호와 충돌하지 않도록 <<<PLACEHOLDER>>> 토큰만 치환합니다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# 그대로 치환할 토큰 (본문·형식 예시 안의 중괄호와 충돌하지 않게 분리)
_PH_PATIENT_ID = "<<<PATIENT_ID>>>"
_PH_SYMPTOMS = "<<<SYMPTOMS>>>"
_PH_HISTORY = "<<<HISTORY>>>"
_PH_TOP_RX = "<<<TOP_RX>>>"
_PH_SIMILAR = "<<<SIMILAR_OUTCOMES>>>"
_PH_OPTIONAL_MENTION = "<<<OPTIONAL_MENTION_BLOCK>>>"
_PH_OPTIONAL_CLINICIAN = "<<<OPTIONAL_CLINICIAN_BLOCK>>>"

PRESCRIPTION_AGENT_PROMPT = """## Role
당신은 ArangoDB 기반 의료 그래프 데이터를 분석하여 최적의 처방(Prescription)을 추천하는 AI 의료 어시스턴트입니다.

## Context
1. 데이터 소스: ArangoDB 그래프 — 문서: visits, diagnoses, prescription_masters, order_lines, special_notes, note_mentions
   엣지: visit_has_diagnosis, visit_has_order, order_refers_prescription, visit_has_note, order_associated_diagnosis,
   note_has_mention(특이사항→mention), diagnosis_has_mention(상병→mention), prescription_has_mention(처방마스터→mention).
   note_mentions 조각(mention) 필드: note_id, visit_id, mention_type, 원문 text, normalized_text, normalized_text_light,
   tokens, is_abbreviation, match_candidates — 적재 후 Arango에서는 논리 mention_id가 문서 _key에만 있으므로(본문 속성 mention_id 없음)
   백엔드·AQL 결과에 _key가 있으면 그것이 mention 식별자입니다.
   CSV `17_rel_diagnosis_has_mention.csv`, `18_rel_prescription_has_mention.csv` 가 이 두 엣지를 적재합니다.
2. 타겟: 현재 환자의 증상, 과거 진단 이력(History), 유사 환자 처방 사례, (선택) 상병·처방과 특이사항 mention 간 직접 연결 요약.
3. 기술 스택: Spring Boot (Back-End), ArangoDB, LangChain.

## Constraints
1. 출력은 반드시 순수 JSON 형태여야 하며, 다른 서술형 문장은 포함하지 마십시오.
2. Rank 1, 2, 3은 각각 '최적 처방', '유사 사례 기반 처방', '보조/대안 처방'의 논리를 따릅니다.
3. **데이터 앵커 + 임상 해석**: 먼저 아래 Patient Context·top_rx·mention·similar_outcomes에 **실제로 등장한** 처방명·코드·증상·토큰을 인용한 뒤, `reason` 안에서만 **일반적인 의학·약리 지식**(약 계열, 상호작용 개념, 감시 항목 등)을 짧게 보강할 수 있습니다. 입력에 없는 진단·처방 **사실**을 새로 만들지는 마십시오.
4. **name 필드(필수)**: top_rx가 구체 처방 객체들의 배열이고 각 행에 처방명 또는 처방코드가 있으면, 세 rank의 `name`은 **그 목록에 있는 처방명(없으면 처방코드)을 문자열 그대로** 사용하십시오. 목록에 없는 영문 제네릭·상품명을 name으로 쓰지 마십시오.
5. **prescription_code 필드(필수)**: 각 추천 항목에 해당하는 처방 코드를 문자열로 넣으십시오. top_rx의 처방코드/prescription_code 값을 우선 사용하고, 데이터가 없으면 `"미기재"`를 사용하십시오.
6. **dosage**: 입력에 용량이 없으면 `"미기재"` 또는 `"데이터에 용량 없음"`만 사용하고, 임의 mg/cc를 지어내지 마십시오.
7. top_rx가 비어 있거나 안내용 메모 한 줄뿐이면, 임의 약품을 name으로 쓰지 말고 `name`에 `"데이터 부족: top_rx 비어 있음"` 등을 쓰고, `prescription_code`는 `"미기재"`로 두고, `reason`에 그 사실과 가능한 일반적 고려만 짧게 적으십시오.

아래의 환자 상태 및 ArangoDB 그래프 조회 결과를 바탕으로 상위 3개의 처방을 추천하십시오.

### Patient Context
- Patient ID: <<<PATIENT_ID>>>
- Current Symptoms: <<<SYMPTOMS>>>
- Medical History: <<<HISTORY>>>

### ArangoDB Graph Insights (AQL Result)
- Top Frequency Prescriptions for Disease: <<<TOP_RX>>>
- Similar Patient Outcomes: <<<SIMILAR_OUTCOMES>>>

<<<OPTIONAL_MENTION_BLOCK>>><<<OPTIONAL_CLINICIAN_BLOCK>>>
### Required JSON Format (Strict)
{
  "prescriptions": [
    {
      "rank": 1,
      "name": "top_rx에 있는 처방명(또는 처방코드)을 그대로",
      "prescription_code": "top_rx에 있는 처방코드(없으면 미기재)",
      "dosage": "미기재 또는 입력에 있는 용량만",
      "reason": "데이터 인용 후, 필요 시 짧은 임상·약리 보강(한국어)"
    },
    { "rank": 2, "name": "...", "prescription_code": "...", "dosage": "...", "reason": "..." },
    { "rank": 3, "name": "...", "prescription_code": "...", "dosage": "...", "reason": "..." }
  ]
}

추천 결과:
"""


def _as_prompt_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value) if value is not None else ""


def _distinct_prescription_row_count(top_rx: Any) -> int:
    """top_rx 배열에서 처방명·코드가 있는 서로 다른 행 수(Arango/코호트 없을 때 희소 판단용)."""
    if top_rx is None or isinstance(top_rx, str):
        return 0
    if not isinstance(top_rx, list):
        return 0
    keys_name = ("처방명", "prescription_name", "name")
    keys_code = ("처방코드", "prescription_code", "code")
    seen: set[tuple[str, str]] = set()
    for row in top_rx:
        if not isinstance(row, dict):
            continue
        name = ""
        for k in keys_name:
            v = row.get(k)
            if v is not None and str(v).strip():
                name = str(v).strip()
                break
        code = ""
        for k in keys_code:
            v = row.get(k)
            if v is not None and str(v).strip() and str(v).strip() != "미기재":
                code = str(v).strip()
                break
        if not name and not code:
            continue
        key = (name, code)
        if key in seen:
            continue
        seen.add(key)
    return len(seen)


def _sparse_top_rx_appendix(top_rx: Any) -> str:
    """고유 처방 < 3일 때만: rank 2·3에 그래프 없이도 실제 약품명 제안 허용(플레이스홀더 금지)."""
    if _distinct_prescription_row_count(top_rx) >= 3:
        return ""
    return """
### Sparse data override (이 섹션은 위 Constraint 4·7보다 우선합니다)
`top_rx`에서 **처방명 또는 처방코드가 있는 서로 다른 행**이 3개 미만입니다. (ArangoDB 미기동·연결 실패, 코호트 AQL 실패,
과거 처방 MySQL 적재가 적은 경우 등으로 흔합니다.)

1. **rank 1**: `top_rx`에 유효 처방 행이 **1건 이상**이면, 그중 임상적으로 가장 핵심인 1건의 **처방명(또는 코드)**을 그대로 사용하십시오.
   유효 행이 **0건**(안내용 `note`만 있는 경우)이면, Patient Context의 상병·증상·history에 맞는 **실제 국내 처방명** 1건을 제안하십시오.
2. **rank 2, 3**: `top_rx`에 남은 **서로 다른** 처방이 부족하면, 상병·증상·history 맥락에서 **임상적으로 타당한 병용·대안 처방**(실제 제품명·성분명)을 채우십시오.
3. **`name`에 금지**: "데이터 부족", "유사 사례 없음", "top_rx 비어 있음" 등 **메타 문구만** 넣는 것. 반드시 **구체 처방명**을 쓰십시오.
4. **rank 2·3**의 `reason` 첫 문장에 반드시 다음 취지를 포함하십시오:
   「Arango 그래프·코호트 데이터가 부족하여 유사 환자 빈도 근거는 없으며, 일반 진료·지침 수준의 추론 제안입니다.」
5. `prescription_code`는 확실할 때만 채우고, 불확실하면 `미기재`로 두어도 됩니다.
6. `dosage`는 입력에 없으면 `미기재` 또는 `데이터에 용량 없음`만 사용하십시오.
"""


def _coerce_mention_links_for_prompt(mention_links: Any) -> Any:
    """
    Arango note_mentions / 엣지 조회 JSON을 프롬프트에 넣기 좋게 통일합니다.

    적재 시 mention_id는 _key로만 존재하는 경우가 많아, _key만 있으면 mention_id를 채웁니다.
    """
    if mention_links is None:
        return None

    def _one(row: Any) -> Any:
        if not isinstance(row, dict):
            return row
        out = dict(row)
        mid = out.get("mention_id")
        if mid is None or (isinstance(mid, str) and not mid.strip()):
            k = out.get("_key")
            if isinstance(k, str) and k.strip():
                out["mention_id"] = k.strip()
        return out

    if isinstance(mention_links, list):
        return [_one(x) for x in mention_links]
    return _one(mention_links)


def _optional_mention_section(mention_links: Any) -> str:
    """diagnosis_has_mention / prescription_has_mention·note_mentions 조회 요약이 있을 때만 블록 생성."""
    if mention_links is None:
        return ""
    if isinstance(mention_links, (list, dict)) and len(mention_links) == 0:
        return ""
    coerced = _coerce_mention_links_for_prompt(mention_links)
    body = _as_prompt_text(coerced).strip()
    if not body:
        return ""
    return (
        "### Mention (note_mentions + edges 16–18, optional)\n"
        "각 행의 text·normalized_text·tokens·match_candidates·mention_type·is_abbreviation을 근거로 삼고, "
        "mention_id가 비어 있으면 _key를 동일 식별자로 간주합니다.\n"
        f"{body}\n\n"
    )


def build_prescription_agent_prompt(
    patient_id: Any,
    symptoms: Any,
    history: Any,
    top_rx: Any,
    similar_outcomes: Any,
    clinician_question: str | None = None,
    mention_links: Any | None = None,
) -> str:
    """
    환자·그래프 인사이트를 넣은 단일 사용자 메시지 본문을 만듭니다.

    LangChain / Spring: 이 문자열 전체를 **user** 메시지로 보내는 것이 가장 단순합니다.
    system 메시지는 짧게 두고(역할·JSON만 출력 등), 긴 지시·데이터는 여기에만 두면 됩니다.

    clinician_question: 의사/화면에서 온 자연어 질문이 있으면 그래프 요약 뒤에 붙습니다. 없으면 생략.
    mention_links: diagnosis_has_mention·prescription_has_mention·note_mentions 기반 AQL/REST 결과(선택).
        note_mentions 본문 필드(note_id, visit_id, mention_type, text, normalized_text, …)와 엣지 메타를 그대로 넣으면 됩니다.
    """
    cq = (clinician_question or "").strip()
    optional_block = (
        f"### Clinician question\n{cq}\n\n" if cq else ""
    )
    base = (
        PRESCRIPTION_AGENT_PROMPT.replace(_PH_PATIENT_ID, _as_prompt_text(patient_id))
        .replace(_PH_SYMPTOMS, _as_prompt_text(symptoms))
        .replace(_PH_HISTORY, _as_prompt_text(history))
        .replace(_PH_TOP_RX, _as_prompt_text(top_rx))
        .replace(_PH_SIMILAR, _as_prompt_text(similar_outcomes))
        .replace(_PH_OPTIONAL_MENTION, _optional_mention_section(mention_links))
        .replace(_PH_OPTIONAL_CLINICIAN, optional_block)
    )
    return base + _sparse_top_rx_appendix(top_rx)


def load_prescription_context_file(path: Path) -> dict[str, Any]:
    """
    JSON 파일에서 컨텍스트를 읽습니다.

    필수 키: patient_id, symptoms, history, top_rx, similar_outcomes
    선택 키: mention_links (note_mentions 문서 또는 16–18번 엣지 조인 결과 배열; _key만 있어도 됨)
    run_prescription_agent.py 의 ``--fetch-top-rx-from-arango`` 로 Arango에서 top_rx 를 채우면 이 필드는 실행 시 덮어써질 수 있음.
    (값은 문자열 또는 JSON 배열/객체 가능)
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    required = ("patient_id", "symptoms", "history", "top_rx", "similar_outcomes")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"prescription context JSON에 필수 키가 없습니다: {missing}")
    out: dict[str, Any] = {k: data[k] for k in required}
    if "mention_links" in data:
        out["mention_links"] = data["mention_links"]
    return out


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_object_from_llm_text(raw: str) -> dict[str, Any]:
    """
    LLM 응답에서 최상위 JSON 객체를 파싱합니다.
    앞뒤 설명문·마크다운 코드 펜스가 있어도 첫 객체를 찾습니다.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("빈 응답입니다.")

    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    dec = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        raise ValueError("JSON 객체 시작 `{` 를 찾을 수 없습니다.")
    obj, _ = dec.raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("최상위 값은 JSON 객체여야 합니다.")
    return obj


def validate_prescriptions_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Required JSON Format 스키마를 검증하고 prescriptions 배열을 반환합니다."""
    rx = data.get("prescriptions")
    if not isinstance(rx, list) or len(rx) != 3:
        raise ValueError('키 "prescriptions" 는 길이 3인 배열이어야 합니다.')

    required_fields = ("rank", "name", "prescription_code", "dosage", "reason")
    parsed: list[tuple[int, dict[str, Any]]] = []
    for i, item in enumerate(rx):
        if not isinstance(item, dict):
            raise ValueError(f"prescriptions[{i}] 는 객체여야 합니다.")
        missing = [k for k in required_fields if k not in item]
        if missing:
            raise ValueError(f"prescriptions[{i}] 에 필수 키가 없습니다: {missing}")
        try:
            r_int = int(item["rank"])  # type: ignore[arg-type]
        except (TypeError, ValueError) as e:
            raise ValueError(f"prescriptions[{i}].rank 은 정수여야 합니다: {item['rank']!r}") from e
        parsed.append((r_int, dict(item)))

    parsed.sort(key=lambda t: t[0])
    ranks_sorted = [t[0] for t in parsed]
    if ranks_sorted != [1, 2, 3]:
        raise ValueError(
            "prescriptions 의 rank 는 1, 2, 3 이 각각 한 번씩 있어야 합니다 "
            f"(정렬 후: {ranks_sorted!r}). 모델이 순서를 바꿨거나 중복 rank 를 냈을 수 있습니다."
        )

    out: list[dict[str, Any]] = []
    for i, (_r, item) in enumerate(parsed):
        item["rank"] = i + 1
        out.append(item)
    return out


def parse_prescriptions_llm_response(raw: str) -> dict[str, Any]:
    """모델 출력을 파싱·검증한 뒤 prescriptions 스키마를 만족하는 dict를 반환합니다."""
    data = extract_json_object_from_llm_text(raw)
    validate_prescriptions_payload(data)
    return data
