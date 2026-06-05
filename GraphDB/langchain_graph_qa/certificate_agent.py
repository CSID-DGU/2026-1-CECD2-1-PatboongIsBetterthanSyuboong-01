# -*- coding: utf-8 -*-
"""
진단서 생성 에이전트용 프롬프트 템플릿.

prescription_agent.py 와 동일한 <<<PLACEHOLDER>>> 토큰 방식 사용.

생성 범위:
- GENERAL  : 일반진단서의 '치료 내용 및 향후 치료에 대한 소견' 필드
- MILITARY : 병무용 진단서의 '증상 및 질병(상해)에 대한 소견' 필드
"""

from __future__ import annotations

from typing import Any

# ── 치환 토큰 ────────────────────────────────────────────────────────────────
_PH_PATIENT_GENDER = "<<<PATIENT_GENDER>>>"
_PH_PATIENT_AGE    = "<<<PATIENT_AGE>>>"
_PH_ENTRY_DATE     = "<<<ENTRY_DATE>>>"
_PH_SYMPTOM        = "<<<SYMPTOM_DETAIL>>>"
_PH_DIAGNOSIS_KIND = "<<<DIAGNOSIS_KIND>>>"
_PH_PURPOSE        = "<<<PURPOSE>>>"
_PH_DISEASES       = "<<<DISEASES>>>"
_PH_DIAGNOSES      = "<<<DIAGNOSES>>>"

# ── 시스템 메시지 ─────────────────────────────────────────────────────────────
SYSTEM_CERTIFICATE = (
    "당신은 대한민국 의료기관의 전문 임상의입니다. "
    "제공된 환자 정보(증상, 상병명, 처방 내역)를 바탕으로 "
    "지정된 진단서 양식 필드에 들어갈 내용만 의학적으로 정확하게 작성합니다. "
    "환자명·날짜·서명·기관명 등 행정 항목은 절대 출력하지 마십시오. "
    "모든 문장은 한국어로 작성하고 마침표(.)로 끝내십시오."
)

# ── 일반진단서 프롬프트 ───────────────────────────────────────────────────────
# 출력 대상: '치료 내용 및 향후 치료에 대한 소견' 필드 (단일 단락)
GENERAL_PROMPT = """\
다음 환자 정보를 바탕으로 일반진단서의 '치료 내용 및 향후 치료에 대한 소견' 필드에 들어갈 내용을 작성하세요.

### 환자 정보
- 성별 / 나이: <<<PATIENT_GENDER>>> / <<<PATIENT_AGE>>>세
- 진료일: <<<ENTRY_DATE>>>
- 주요 증상: <<<SYMPTOM_DETAIL>>>
- 진단 구분: <<<DIAGNOSIS_KIND>>>
- 용도: <<<PURPOSE>>>

### 상병명
<<<DISEASES>>>

### 처방 내역
<<<DIAGNOSES>>>

### 작성 지침
1. 이 필드는 반드시 '치료 내용 및 향후 치료에 대한 소견'이어야 하며, 진료 기록 요약이나 상병·처방 목록 나열로 작성하지 마세요.
2. 첫 문장에는 현재 시행했거나 시행 중인 치료 내용(약물치료, 처치, 안정, 경과 관찰 등)을 상병·증상과 연결해 서술하세요.
3. 두 번째 이후 문장에는 향후 치료 계획(추적 관찰, 추가 검사, 약물 조절, 재내원, 생활 제한/휴식 필요성 등)을 구체적으로 작성하세요.
4. 처방약 이름은 필요한 경우 치료 목적과 함께 자연스럽게 언급하되, 투약 목록을 그대로 반복하지 마세요.
5. 진단 구분이 '임상적 추정'이면 확정 표현을 피하고 관찰·추정·추적 필요성을 중심으로 작성하세요.
6. 진단 구분이 '최종 진단'이면 확정된 진단에 근거한 치료 경과와 향후 계획을 중심으로 작성하세요.
7. 용도에 맞게 문체와 강조점을 조정하세요. 사내/학교 제출용은 치료와 휴식 필요성을, 군대/병무용은 기능 제한과 추적 관찰 필요성을, 보험사 제출용은 진단·치료 근거와 향후 치료 계획을, 법적 증빙용은 객관적이고 단정한 의학 소견을 우선하세요.
8. 환자명, 성별, 나이, 진료일, 제목, 상병명 목록, 처방 내역 제목 같은 행정 항목은 절대 포함하지 마세요.
9. 3~5문장의 단일 단락으로 작성하고 모든 문장은 마침표(.)로 끝내세요.

치료 내용 및 향후 치료에 대한 소견:"""

# ── 병무용 진단서 프롬프트 ───────────────────────────────────────────────────
# 출력 대상: '증상 및 질병(상해)에 대한 소견' 필드 (단일 단락)
MILITARY_PROMPT = """\
다음 환자 정보를 바탕으로 병무용 진단서의 '증상 및 질병(상해)에 대한 소견' 필드에 들어갈 내용을 작성하세요.

### 환자 정보
- 성별 / 나이: <<<PATIENT_GENDER>>> / <<<PATIENT_AGE>>>세
- 진료일: <<<ENTRY_DATE>>>
- 주요 증상: <<<SYMPTOM_DETAIL>>>
- 진단 구분: <<<DIAGNOSIS_KIND>>>
- 용도: <<<PURPOSE>>>

### 상병명
<<<DISEASES>>>

### 처방 내역
<<<DIAGNOSES>>>

### 작성 지침
1. 병무용 양식의 소견란이지만, 단순 진료 내용 요약이 아니라 현재 치료 내용과 향후 치료·경과 관찰 필요성을 함께 작성하세요.
2. 상병명과 증상의 연관성, 기능 제한 가능성, 현재 시행 중인 치료를 3~5문장으로 서술하세요.
3. 향후 치료 계획에는 추적 관찰, 추가 평가, 약물/물리치료 지속 여부, 증상 지속 시 재평가 필요성을 포함하세요.
4. 진단 구분이 '임상적 추정'이면 확정 표현을 피하고 현재 소견상 의심되는 상태와 추가 평가·경과 관찰 필요성을 중심으로 작성하세요.
5. 진단 구분이 '최종 진단'이면 확정된 진단과 기능 제한 가능성, 치료 경과 및 향후 계획을 중심으로 작성하세요.
6. 병역 판정에 참고 가능한 증상 지속성, 기능 제한, 추적 관찰 필요성을 객관적으로 설명하세요.
7. 환자명, 성별, 나이, 진료일, 제목, 상병명 목록, 처방 내역 제목 같은 행정 항목은 절대 포함하지 마세요.
8. 단일 단락으로 작성하고 모든 문장은 마침표(.)로 끝내세요.

증상 및 질병(상해)에 대한 소견:"""


def _format_diseases(diseases: list[dict[str, Any]]) -> str:
    if not diseases:
        return "상병명 정보 없음"
    lines = []
    for d in diseases:
        code   = d.get("code", "")
        name   = d.get("name", "")
        degree = d.get("degree") or ""
        suffix = f" ({degree})" if degree else ""
        lines.append(f"- [{code}] {name}{suffix}")
    return "\n".join(lines)


def _format_diagnoses(diagnoses: list[dict[str, Any]]) -> str:
    if not diagnoses:
        return "처방 내역 없음"
    lines = []
    for d in diagnoses:
        code = d.get("code", "")
        name = d.get("name", "")
        dose = d.get("dose", 0)
        time = d.get("time", 0)
        days = d.get("days", 0)
        lines.append(f"- [{code}] {name} {dose}mg 1일 {time}회 {days}일분")
    return "\n".join(lines)


def build_certificate_agent_prompt(
    patient_gender: str,
    patient_age: int,
    entry_date: str,
    symptom_detail: str | None,
    diagnosis_kind: str | None,
    purpose: str | None,
    diseases: list[dict[str, Any]],
    diagnoses: list[dict[str, Any]],
    certificate_type: str = "GENERAL",
) -> str:
    """환자 정보를 넣은 단일 사용자 메시지 본문을 반환합니다."""
    template = MILITARY_PROMPT if certificate_type == "MILITARY" else GENERAL_PROMPT
    return (
        template
        .replace(_PH_PATIENT_GENDER, patient_gender or "")
        .replace(_PH_PATIENT_AGE,    str(patient_age))
        .replace(_PH_ENTRY_DATE,     entry_date or "")
        .replace(_PH_SYMPTOM,        symptom_detail or "특이 증상 없음")
        .replace(_PH_DIAGNOSIS_KIND, diagnosis_kind or "미선택")
        .replace(_PH_PURPOSE,        purpose or "미선택")
        .replace(_PH_DISEASES,       _format_diseases(diseases))
        .replace(_PH_DIAGNOSES,      _format_diagnoses(diagnoses))
    )
