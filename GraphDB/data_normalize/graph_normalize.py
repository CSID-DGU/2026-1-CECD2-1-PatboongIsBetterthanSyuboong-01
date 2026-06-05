"""
엑셀 원본 → 노드/관계 DataFrame 검증 후 UTF-8-SIG CSV 저장.
Steps 2–10 (컬럼 고정, 문자열 정리, norm, ID, 중복 제거, 노드/관계, 검증, 저장).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from note_mentions import build_mention_tables, normalize_mention_text
from read_excel import read_excel
from text_utils import (
    clean_string_cell,
    norm_code,
    norm_text,
    normalize_column_names,
)

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

CANONICAL_COLS = [
    "상병코드",
    "내원번호",
    "처방시퀀스",
    "처방코드",
    "처방명",
    "특이사항",
]

def _sha16(*parts: str) -> str:
    s = "|".join(parts)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def stable_note_id_visit_scoped(visit_id: Any, 특이사항_norm: Any) -> Any:
    """방문별 특이사항 노드: 빈 값은 NA (NOTE_NA 미사용)."""
    if pd.isna(visit_id):
        return pd.NA
    if pd.isna(특이사항_norm):
        return pd.NA
    t = str(특이사항_norm).strip()
    if t == "":
        return pd.NA
    return f"NOTE_{_sha16(str(visit_id), t)}"


def structural_order_line_id(visit_id: Any, 처방시퀀스_norm: Any, prescription_code: Any) -> Any:
    """visit + 처방시퀀스 + 처방코드 기준 구조 키."""
    if pd.isna(visit_id) or pd.isna(prescription_code):
        return pd.NA
    seq = "" if pd.isna(처방시퀀스_norm) else str(처방시퀀스_norm)
    code = "" if pd.isna(prescription_code) else str(prescription_code)
    return f"OL_{_sha16(str(visit_id), seq, code)}"


def _row_hash_from_norms(r: pd.Series) -> str:
    parts = [
        str(r.get("상병코드_norm", "")),
        str(r.get("내원번호_norm", "")),
        str(r.get("처방시퀀스_norm", "")),
        str(r.get("처방코드_norm", "")),
        str(r.get("처방명_norm", "")),
        str(r.get("특이사항_norm", "")),
    ]
    return _sha16(*parts)


def duplicate_group_key_row(r: pd.Series) -> str:
    return f"DUP_{_row_hash_from_norms(r)}"


def step_clean_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Step 3: 각 컬럼을 문자열 정리 규칙으로 통일."""
    out = df.copy()
    for c in CANONICAL_COLS:
        out[c] = out[c].map(clean_string_cell)
    return out


def step_add_norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Step 4: *_norm 컬럼."""
    out = df.copy()
    out["상병코드_norm"] = out["상병코드"].map(norm_code)
    out["내원번호_norm"] = out["내원번호"].map(norm_text)
    out["처방시퀀스_norm"] = out["처방시퀀스"].map(clean_string_cell)
    out["처방코드_norm"] = out["처방코드"].map(norm_code)
    out["처방명_norm"] = out["처방명"].map(norm_text)
    out["특이사항_norm"] = out["특이사항"].map(norm_text)
    return out


def step_add_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Step 5: ID 컬럼."""
    out = df.copy()

    def visit_id_from_row(r: pd.Series) -> Any:
        if pd.isna(r["내원번호_norm"]):
            return pd.NA
        return f"VISIT_{r['내원번호_norm']}"

    out["visit_id"] = out.apply(visit_id_from_row, axis=1)
    out["diagnosis_code"] = out["상병코드_norm"]
    out["prescription_code"] = out["처방코드_norm"]
    out["duplicate_group_key"] = out.apply(duplicate_group_key_row, axis=1)
    out["order_line_id"] = out.apply(
        lambda r: structural_order_line_id(
            r["visit_id"],
            r["처방시퀀스_norm"],
            r["prescription_code"],
        ),
        axis=1,
    )
    out["note_id"] = out.apply(
        lambda r: stable_note_id_visit_scoped(r["visit_id"], r["특이사항_norm"]),
        axis=1,
    )
    return out


def step_mark_and_drop_full_duplicates(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Step 6: 완전 중복행 플래그 및 제거. (제거 전 전체 df + 플래그, 제거 후 df, 메타)"""
    cols_for_dup = CANONICAL_COLS
    n_before = len(df)
    dup_mask = df.duplicated(subset=cols_for_dup, keep="first")
    flagged = df.copy()
    flagged["is_duplicate_row"] = dup_mask
    out_dedup = df.loc[~dup_mask].copy()
    n_after = len(out_dedup)
    meta = {
        "step": "full_duplicate_drop",
        "rows_before": n_before,
        "rows_after": n_after,
        "removed_rows": n_before - n_after,
        "duplicate_row_count": int(dup_mask.sum()),
    }
    return out_dedup, flagged, meta


def _first_mode_canonical(s: pd.Series) -> Any:
    s = s.dropna()
    if s.empty:
        return pd.NA
    return s.value_counts().index[0]


def build_node_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Step 7: 노드 테이블 (drop_duplicates / groupby)."""
    visit_nodes = (
        df.groupby("visit_id", dropna=False)
        .agg(
            내원번호_norm=("내원번호_norm", "first"),
        )
        .reset_index()
    )

    diagnosis_nodes = (
        df.groupby("diagnosis_code", dropna=False)
        .agg(
            상병코드_norm=("상병코드_norm", "first"),
        )
        .reset_index()
    )

    prescription_master_nodes = (
        df.groupby("prescription_code", dropna=False)
        .agg(
            canonical_name=("처방명_norm", _first_mode_canonical),
            name_variant_count=("처방명_norm", pd.Series.nunique),
        )
        .reset_index()
    )
    prescription_master_nodes["review_flag"] = (
        prescription_master_nodes["name_variant_count"] > 1
    )

    order_line_nodes = (
        df.groupby("order_line_id", dropna=False)
        .agg(
            visit_id=("visit_id", "first"),
            처방시퀀스_norm=("처방시퀀스_norm", "first"),
            처방코드_norm=("처방코드_norm", "first"),
            prescription_code=("prescription_code", "first"),
            처방명_norm=("처방명_norm", "first"),
            name_variant_count_within_same_structural_key=("처방명_norm", pd.Series.nunique),
        )
        .reset_index()
    )
    order_line_nodes["raw_name_conflict_flag"] = (
        order_line_nodes["name_variant_count_within_same_structural_key"] > 1
    )

    df_note = df[df["note_id"].notna()].copy()
    special_note_nodes = (
        df_note.groupby("note_id", dropna=False)
        .agg(
            visit_id=("visit_id", "first"),
            특이사항_norm=("특이사항_norm", "first"),
        )
        .reset_index()
    )

    return {
        "visit_nodes": visit_nodes,
        "diagnosis_nodes": diagnosis_nodes,
        "prescription_master_nodes": prescription_master_nodes,
        "order_line_nodes": order_line_nodes,
        "special_note_nodes": special_note_nodes,
    }


def build_relationship_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Step 8: 관계 (pair distinct). 빈 특이사항은 visit_has_note 에 포함하지 않음."""
    vhd = df[["visit_id", "diagnosis_code"]].drop_duplicates()
    vho = df[["visit_id", "order_line_id"]].drop_duplicates()
    orp = df[["order_line_id", "prescription_code"]].drop_duplicates()
    df_note_edge = df[df["note_id"].notna()]
    vhn = df_note_edge[["visit_id", "note_id"]].drop_duplicates()
    oad = df[["order_line_id", "diagnosis_code"]].drop_duplicates()
    return {
        "visit_has_diagnosis": vhd,
        "visit_has_order": vho,
        "order_refers_to_prescription": orp,
        "visit_has_note": vhn,
        "order_associated_with_diagnosis": oad,
    }


# --- Diagnosis / Prescription ↔ Mention (의미: 임상 동일이 아니라 동일 방문·연관 가능성) ---
# 관계 의미: diagnosis_related_mention / prescription_related_mention 에 대응하는 엣지 CSV 명은
# diagnosis_has_mention, prescription_has_mention.

DIAGNOSIS_SYNONYMS: dict[str, tuple[str, ...]] = {
    "I10": ("고혈압", "htn", "혈압"),
    "E11": ("당뇨", "dm", "당뇨병"),
    "E78": ("고지혈증", "dyslipidemia", "지질"),
    "I50": ("심부전", "hf"),
    "N18": ("ckd", "신부전", "만성신부전"),
    "J44": ("copd", "폐쇄성"),
}


def _diagnosis_mention_link(
    diagnosis_code: str,
    text: str,
    normalized: str,
) -> tuple[str, float, bool]:
    dc = str(diagnosis_code).strip().upper()
    raw_u = (text or "").upper()
    nt = (normalized or "").lower()
    if dc and dc in raw_u:
        return "TERM_MATCH", 0.9, False
    syns = DIAGNOSIS_SYNONYMS.get(dc, ())
    for s in syns:
        if s.lower() in nt:
            return "SYNONYM_MATCH", 0.78, False
    return "VISIT_JOIN", 0.32, True


def build_diagnosis_mention_edges(
    df_dedup: pd.DataFrame,
    mention_nodes: pd.DataFrame,
) -> pd.DataFrame:
    """같은 visit 내 CONDITION mention ↔ 상병 (1차: CONDITION만, 코드/동의어 일치 우선)."""
    cols = ["diagnosis_code", "mention_id", "link_source", "confidence", "review_flag"]
    if mention_nodes.empty or "mention_type" not in mention_nodes.columns:
        return pd.DataFrame(columns=cols)
    mcond = mention_nodes[mention_nodes["mention_type"] == "CONDITION"].copy()
    if mcond.empty:
        return pd.DataFrame(columns=cols)
    dx_visit = df_dedup[["visit_id", "diagnosis_code"]].drop_duplicates()
    rows: list[dict[str, Any]] = []
    has_norm = "normalized_text" in mcond.columns
    for _, m in mcond.iterrows():
        vid = str(m["visit_id"]).strip()
        mid = m["mention_id"]
        text = str(m.get("text", ""))
        nt = str(m["normalized_text"]) if has_norm and pd.notna(m.get("normalized_text")) else normalize_mention_text(text)
        for dc in dx_visit[dx_visit["visit_id"].astype(str) == vid]["diagnosis_code"]:
            if pd.isna(dc):
                continue
            src, conf, rev = _diagnosis_mention_link(str(dc), text, nt)
            rows.append(
                {
                    "diagnosis_code": str(dc).strip(),
                    "mention_id": mid,
                    "link_source": src,
                    "confidence": conf,
                    "review_flag": bool(rev),
                }
            )
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows).drop_duplicates(subset=["diagnosis_code", "mention_id"], keep="first")
    return out


def _prescription_mention_link(
    처방명_norm: Any,
    text: str,
    normalized: str,
) -> tuple[str, float, bool]:
    mt = (text or "").lower()
    nt = (normalized or mt).lower()
    pn = "" if pd.isna(처방명_norm) else str(처방명_norm).strip().lower()
    if not pn:
        return "VISIT_JOIN", 0.28, True
    if len(pn) >= 2 and (pn in mt or pn in nt):
        return "TERM_MATCH", 0.84, False
    for tok in re.split(r"[\s,]+", pn):
        tok = tok.strip()
        if len(tok) >= 3 and tok in mt:
            return "TERM_MATCH", 0.76, False
    return "VISIT_JOIN", 0.3, True


def build_prescription_mention_edges(
    df_dedup: pd.DataFrame,
    mention_nodes: pd.DataFrame,
) -> pd.DataFrame:
    """같은 visit 내 CONDITION·LAB mention ↔ 처방 마스터 (1차: 타입 필터, 키워드 일치 시 가중)."""
    cols = ["prescription_code", "mention_id", "link_source", "confidence", "review_flag"]
    if mention_nodes.empty or "mention_type" not in mention_nodes.columns:
        return pd.DataFrame(columns=cols)
    mrx = mention_nodes[mention_nodes["mention_type"].isin(["CONDITION", "LAB"])].copy()
    if mrx.empty:
        return pd.DataFrame(columns=cols)
    rx_visit = (
        df_dedup.groupby(["visit_id", "prescription_code"], dropna=False)
        .agg(처방명_norm=("처방명_norm", "first"))
        .reset_index()
    )
    rows: list[dict[str, Any]] = []
    has_norm = "normalized_text" in mrx.columns
    for _, m in mrx.iterrows():
        vid = str(m["visit_id"]).strip()
        mid = m["mention_id"]
        text = str(m.get("text", ""))
        nt = str(m["normalized_text"]) if has_norm and pd.notna(m.get("normalized_text")) else normalize_mention_text(text)
        sub = rx_visit[rx_visit["visit_id"].astype(str) == vid]
        for _, rx in sub.iterrows():
            pcode = rx["prescription_code"]
            if pd.isna(pcode):
                continue
            src, conf, rev = _prescription_mention_link(rx.get("처방명_norm"), text, nt)
            rows.append(
                {
                    "prescription_code": str(pcode).strip(),
                    "mention_id": mid,
                    "link_source": src,
                    "confidence": conf,
                    "review_flag": bool(rev),
                }
            )
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows).drop_duplicates(subset=["prescription_code", "mention_id"], keep="first")
    return out


def _assert_unique_key(df: pd.DataFrame, key: str, name: str) -> list[str]:
    errs: list[str] = []
    if df[key].isna().any():
        errs.append(f"{name}: 키 {key!r} 에 null 이 있습니다.")
    if df[key].duplicated().any():
        errs.append(f"{name}: 키 {key!r} 가 unique 하지 않습니다.")
    return errs


def validate_graph(
    nodes: dict[str, pd.DataFrame],
    rels: dict[str, pd.DataFrame],
) -> list[str]:
    """Step 9: 검증."""
    errs: list[str] = []
    errs += _assert_unique_key(nodes["visit_nodes"], "visit_id", "visit_nodes")
    errs += _assert_unique_key(nodes["diagnosis_nodes"], "diagnosis_code", "diagnosis_nodes")
    errs += _assert_unique_key(nodes["prescription_master_nodes"], "prescription_code", "prescription_master_nodes")
    errs += _assert_unique_key(nodes["order_line_nodes"], "order_line_id", "order_line_nodes")
    errs += _assert_unique_key(nodes["special_note_nodes"], "note_id", "special_note_nodes")
    if not nodes["note_mention_nodes"].empty:
        errs += _assert_unique_key(nodes["note_mention_nodes"], "mention_id", "note_mention_nodes")

    visit_ids = set(nodes["visit_nodes"]["visit_id"].dropna().astype(str))
    diag_ids = set(nodes["diagnosis_nodes"]["diagnosis_code"].dropna().astype(str))
    presc_ids = set(nodes["prescription_master_nodes"]["prescription_code"].dropna().astype(str))
    order_ids = set(nodes["order_line_nodes"]["order_line_id"].dropna().astype(str))
    note_ids = set(nodes["special_note_nodes"]["note_id"].dropna().astype(str))
    mention_ids = (
        set(nodes["note_mention_nodes"]["mention_id"].dropna().astype(str))
        if not nodes["note_mention_nodes"].empty
        else set()
    )

    def check_edge(
        rel_name: str,
        df: pd.DataFrame,
        col_src: str,
        col_dst: str,
        valid_src: set[str],
        valid_dst: set[str],
    ) -> None:
        nonlocal errs
        bad_src = ~df[col_src].astype(str).isin(valid_src)
        bad_dst = ~df[col_dst].astype(str).isin(valid_dst)
        if bad_src.any():
            errs.append(f"{rel_name}: {col_src} 가 노드에 없는 행 {bad_src.sum()}건")
        if bad_dst.any():
            errs.append(f"{rel_name}: {col_dst} 가 노드에 없는 행 {bad_dst.sum()}건")
        dup = df.duplicated(subset=[col_src, col_dst])
        if dup.any():
            errs.append(f"{rel_name}: 중복 edge {dup.sum()}건")

    check_edge(
        "visit_has_diagnosis",
        rels["visit_has_diagnosis"],
        "visit_id",
        "diagnosis_code",
        visit_ids,
        diag_ids,
    )
    check_edge(
        "visit_has_order",
        rels["visit_has_order"],
        "visit_id",
        "order_line_id",
        visit_ids,
        order_ids,
    )
    check_edge(
        "order_refers_to_prescription",
        rels["order_refers_to_prescription"],
        "order_line_id",
        "prescription_code",
        order_ids,
        presc_ids,
    )
    check_edge(
        "visit_has_note",
        rels["visit_has_note"],
        "visit_id",
        "note_id",
        visit_ids,
        note_ids,
    )
    check_edge(
        "order_associated_with_diagnosis",
        rels["order_associated_with_diagnosis"],
        "order_line_id",
        "diagnosis_code",
        order_ids,
        diag_ids,
    )
    if mention_ids:
        check_edge(
            "note_has_mention",
            rels["note_has_mention"],
            "note_id",
            "mention_id",
            note_ids,
            mention_ids,
        )

    if not rels["diagnosis_has_mention"].empty:
        check_edge(
            "diagnosis_has_mention",
            rels["diagnosis_has_mention"],
            "diagnosis_code",
            "mention_id",
            diag_ids,
            mention_ids,
        )
    if not rels["prescription_has_mention"].empty:
        check_edge(
            "prescription_has_mention",
            rels["prescription_has_mention"],
            "prescription_code",
            "mention_id",
            presc_ids,
            mention_ids,
        )

    return errs


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def run_pipeline() -> tuple[list[str], pd.DataFrame]:
    """전체 실행. (검증 오류 목록, 프로파일링 요약 DataFrame) 반환."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    profile_rows: list[dict[str, Any]] = []

    raw = read_excel(sheet_name=0)
    profile_rows.append({"step": "load_excel", "rows": len(raw), "note": ""})

    # Step 2
    df = normalize_column_names(raw, CANONICAL_COLS)
    profile_rows.append({"step": "column_names_fixed", "rows": len(df), "note": ""})

    # Step 3–4–5 (중복 제거 전 전체 컬럼 보존용으로 먼저 norm/id까지)
    df = step_clean_base_columns(df)
    df = step_add_norm_columns(df)
    df = step_add_ids(df)

    profile_rows.append({"step": "after_id_columns", "rows": len(df), "note": ""})

    df_dedup, df_dup_flagged, dup_meta = step_mark_and_drop_full_duplicates(df)
    save_csv(
        df_dup_flagged,
        LOGS_DIR / "step06_full_row_duplicate_flags.csv",
    )
    profile_rows.append(
        {
            "step": dup_meta["step"],
            "rows": dup_meta["rows_after"],
            "note": (
                f"before={dup_meta['rows_before']} removed={dup_meta['removed_rows']} "
                f"is_duplicate_row_true={dup_meta['duplicate_row_count']}"
            ),
        },
    )

    # 제거된 행에는 is_duplicate_row 미포함 → 로그만으로 충분
    nodes = build_node_tables(df_dedup)
    rels = build_relationship_tables(df_dedup)

    mention_nodes, rel_note_mention = build_mention_tables(nodes["special_note_nodes"])
    nodes["note_mention_nodes"] = mention_nodes
    rels["note_has_mention"] = rel_note_mention
    rels["diagnosis_has_mention"] = build_diagnosis_mention_edges(df_dedup, mention_nodes)
    rels["prescription_has_mention"] = build_prescription_mention_edges(df_dedup, mention_nodes)

    errs = validate_graph(nodes, rels)

    out_map = {
        "01_visit_nodes.csv": nodes["visit_nodes"],
        "02_diagnosis_nodes.csv": nodes["diagnosis_nodes"],
        "03_prescription_master_nodes.csv": nodes["prescription_master_nodes"],
        "04_order_line_nodes.csv": nodes["order_line_nodes"],
        "05_special_note_nodes.csv": nodes["special_note_nodes"],
        "11_rel_visit_has_diagnosis.csv": rels["visit_has_diagnosis"],
        "12_rel_visit_has_order.csv": rels["visit_has_order"],
        "13_rel_order_refers_to_prescription.csv": rels["order_refers_to_prescription"],
        "14_rel_visit_has_note.csv": rels["visit_has_note"],
        "15_rel_order_associated_with_diagnosis.csv": rels["order_associated_with_diagnosis"],
        "06_note_mention_nodes.csv": nodes["note_mention_nodes"],
        "16_rel_note_has_mention.csv": rels["note_has_mention"],
        "17_rel_diagnosis_has_mention.csv": rels["diagnosis_has_mention"],
        "18_rel_prescription_has_mention.csv": rels["prescription_has_mention"],
    }
    for name, frame in out_map.items():
        save_csv(frame, OUTPUT_DIR / name)

    summary = pd.DataFrame(profile_rows)
    summary["rows"] = summary["rows"].astype("Int64")
    extra = pd.DataFrame(
        [
            {"step": "nodes_visit", "rows": len(nodes["visit_nodes"]), "note": ""},
            {"step": "nodes_diagnosis", "rows": len(nodes["diagnosis_nodes"]), "note": ""},
            {"step": "nodes_prescription_master", "rows": len(nodes["prescription_master_nodes"]), "note": ""},
            {
                "step": "nodes_order_line",
                "rows": len(nodes["order_line_nodes"]),
                "note": f"fact_rows_after_dedup={len(df_dedup)}",
            },
            {"step": "nodes_special_note", "rows": len(nodes["special_note_nodes"]), "note": ""},
            {"step": "nodes_note_mention", "rows": len(nodes["note_mention_nodes"]), "note": ""},
            {"step": "rels_note_has_mention", "rows": len(rels["note_has_mention"]), "note": ""},
            {"step": "rels_diagnosis_has_mention", "rows": len(rels["diagnosis_has_mention"]), "note": ""},
            {"step": "rels_prescription_has_mention", "rows": len(rels["prescription_has_mention"]), "note": ""},
            {
                "step": "validation_ok",
                "rows": len(errs),
                "note": "; ".join(errs) if errs else "ok",
            },
        ]
    )
    profiling = pd.concat([summary, extra], ignore_index=True)
    save_csv(profiling, LOGS_DIR / "profiling_summary.csv")

    return errs, profiling


if __name__ == "__main__":
    errors, prof = run_pipeline()
    print(prof.to_string(index=False))
    if errors:
        print("--- 검증 경고/오류 ---")
        for e in errors:
            print(e)
        raise SystemExit(1)
    print("완료: output/*.csv, logs/profiling_summary.csv")
