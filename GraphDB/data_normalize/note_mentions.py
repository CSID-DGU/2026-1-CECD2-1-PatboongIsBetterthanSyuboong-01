"""
특이사항(special_notes) 텍스트를 조각(mention) 노드로 분해해 검색·임베딩에 쓰기 위한 유틸.

mention_type (대문자 스키마):
  CONDITION  — 질환/증상 추정 조각
  LAB        — 검사 수치·패턴 (Hb, T-score, %, MMSE 등)
  ADMIN      — 행정·간호·보호자·기구 등 비임상 태그
  FRAGMENT   — 기타 짧은 조각 (문장 분리 잔여)
"""
from __future__ import annotations

import hashlib
import html
import re
from typing import Any

import pandas as pd

# 검사/수치
_RE_LAB = re.compile(
    r"(?i)\b("
    r"hb\b|혈색소|t-?score|mmse|gds|egfr|hba1c|crp|bmd|egd|cfs|"
    r"c-?reactive|creatinine|glucose|"
    r"\d+\.?\d*\s*%|"
    r"\d+\s*/\s*\d+\s*/\s*\d+|"
    r"\d+\s*/\s*\d+///\d+|"  # 원본 날짜 패턴 일부
    r"occult|pancytopenia|anemia|ckd\s*\("
    r")\b"
)
# 행정·간호·기구
_RE_ADMIN = re.compile(
    r"(?i)("
    r"보호자|통화|장기요양|방문간호|등급|l-?tube|foley|가루약|"
    r"본인부담|초과|재택|요양|지시서"
    r")"
)
# 흔한 영문 약어 (질환 추정)
_RE_COND_ABBR = re.compile(
    r"(?i)\b("
    r"htn|dm|ckd|hcc|mdd|bph|pci|lad|rca|pci|hf|gi|egd|"
    r"parkinson|dementia|osteoporosis|epilepsy|sah|tbc"
    r")\b"
)


def _sha16(*parts: str) -> str:
    s = "|".join(parts)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _strip_html(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def _split_fragments(raw: str) -> list[str]:
    """쉼표·슬래시·구분자 기준 1차 분리 (과도한 쪼개기 방지 위해 길이 하한)."""
    t = _strip_html(raw)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return []
    # 긴 구분 시퀀스
    t = re.sub(r"///+", " / ", t)
    parts = re.split(r"[\n\r,;|]+|(?:\s+/\s+)|(?:\s+-\s+(?=[A-Z가-힣]))", t)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < 2:
            continue
        # 여전히 긴 조각은 ' - ' 로 2차 분리 (짧은 세그먼트만)
        if len(p) > 120 and " - " in p:
            for sub in p.split(" - "):
                sub = sub.strip()
                if len(sub) >= 2:
                    out.append(sub)
        else:
            out.append(p)
    return out


def classify_mention_type(text: str) -> str:
    if _RE_LAB.search(text):
        return "LAB"
    if _RE_ADMIN.search(text):
        return "ADMIN"
    if _RE_COND_ABBR.search(text):
        return "CONDITION"
    # 한글 질환명 다수 (짧은 명사 나열)
    if re.search(r"[가-힣]{2,}", text) and len(text) <= 80:
        return "CONDITION"
    return "FRAGMENT"


def mention_id_for(note_id: str, idx: int, text: str) -> str:
    return f"MENTION_{_sha16(str(note_id), str(idx), text[:200])}"


# 약어 → 표준 토큰 (normalized_text 보강용, edge 매칭 2차에 활용)
_ABBR_EXPANSIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bhtn\b"), "고혈압"),
    (re.compile(r"(?i)\bdm\b"), "당뇨"),
    (re.compile(r"(?i)\bckd\b"), "만성신질환"),
    (re.compile(r"(?i)\bdementia\b"), "치매"),
]


def normalize_mention_text(text: str) -> str:
    """소문자·공백 정리 + 흔한 영문 약어를 한글 토큰으로 치환한 문자열."""
    t = _strip_html(text)
    t = re.sub(r"\s+", " ", t).strip().lower()
    for pat, repl in _ABBR_EXPANSIONS:
        t = pat.sub(repl, t)
    return t


def normalize_mention_text_light(text: str) -> str:
    """괄호·숫자·특수문자 완화 버전 (느슨한 매칭용)."""
    t = normalize_mention_text(text)
    t = re.sub(r"[()（）\[\]【】]", " ", t)
    t = re.sub(r"\d+\.?\d*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def mention_tokens_pipe(text: str) -> str:
    """간단 토큰: 공백/슬래시 분리 후 | 구분."""
    t = normalize_mention_text_light(text)
    parts = re.split(r"[/|\s]+", t)
    return "|".join(p for p in parts if len(p) >= 1)


def is_abbreviation_mention(text: str) -> bool:
    return bool(_RE_COND_ABBR.search(text)) or bool(re.search(r"(?i)\b(htn|dm|ckd)\b", text))


def match_candidates_pipe(text: str) -> str:
    """동의어/확장 후보를 '|'로 나열 (추후 사전 연동 시 확장)."""
    base = normalize_mention_text(text)
    light = normalize_mention_text_light(text)
    cands = {base, light, text.strip().lower()}
    return "|".join(c for c in cands if c)


def build_mention_tables(special_note_nodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    special_note_nodes: columns note_id, visit_id, 특이사항_norm

    Returns:
        mention_nodes: mention_id, note_id, visit_id, mention_type, text,
            normalized_text, normalized_text_light, tokens, is_abbreviation, match_candidates
        rel_note_has_mention: note_id, mention_id
    """
    required = {"note_id", "visit_id", "특이사항_norm"}
    if not required.issubset(set(special_note_nodes.columns)):
        raise ValueError(f"special_note_nodes columns must include {required}")

    mention_rows: list[dict[str, Any]] = []
    rel_rows: list[dict[str, Any]] = []

    for _, row in special_note_nodes.iterrows():
        note_id = row.get("note_id")
        visit_id = row.get("visit_id")
        text = row.get("특이사항_norm")
        if pd.isna(note_id) or pd.isna(text):
            continue
        note_id_s = str(note_id).strip()
        visit_s = "" if pd.isna(visit_id) else str(visit_id).strip()
        raw = str(text).strip()
        frags = _split_fragments(raw)
        if not frags:
            continue
        for i, frag in enumerate(frags):
            mid = mention_id_for(note_id_s, i, frag)
            mtype = classify_mention_type(frag)
            nt = normalize_mention_text(frag)
            ntl = normalize_mention_text_light(frag)
            mention_rows.append(
                {
                    "mention_id": mid,
                    "note_id": note_id_s,
                    "visit_id": visit_s,
                    "mention_type": mtype,
                    "text": frag,
                    "normalized_text": nt,
                    "normalized_text_light": ntl,
                    "tokens": mention_tokens_pipe(frag),
                    "is_abbreviation": is_abbreviation_mention(frag),
                    "match_candidates": match_candidates_pipe(frag),
                }
            )
            rel_rows.append({"note_id": note_id_s, "mention_id": mid})

    mentions_df = pd.DataFrame(mention_rows)
    rel_df = pd.DataFrame(rel_rows)
    return mentions_df, rel_df
