#!/usr/bin/env python3
"""
`output/` CSV를 읽어 ArangoDB에 노드·엣지 컬렉션으로 적재

추가(선택): ``06_note_mention_nodes.csv``, ``16_rel_note_has_mention.csv``,
``17_rel_diagnosis_has_mention.csv``, ``18_rel_prescription_has_mention.csv`` — 없으면 해당 엣지만 비어 있음.

연결 정보 우선순위: 환경 변수 > Back-End application-local.properties > 기본값

환경 변수:
  ARANGO_HOST, ARANGO_PORT, ARANGO_USER, ARANGO_PASSWORD, ARANGO_DATABASE

실행 (data_normalize 디렉터리에서):
  pip install -r requirements.txt
  python import_to_arango.py
  python import_to_arango.py --append     # 비우지 않고 덮어쓰기(문서는 _key 기준, 엣지는 해시 키로 중복 방지)
  python import_to_arango.py --dry-run    # DB 없이 행 수만 확인
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

try:
    from arango import ArangoClient
    from arango.exceptions import ArangoError
except ImportError:
    ArangoClient = None  # type: ignore
    ArangoError = Exception  # type: ignore

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
SPRING_LOCAL = (
    REPO_ROOT / "Back-End" / "src" / "main" / "resources" / "application-local.properties"
)

# 문서 컬렉션 (기존 Patient / Disease / Diagnose 와 이름 충돌 없음)
COL_VISITS = "visits"
COL_DIAGNOSES = "diagnoses"
COL_PRESCRIPTION_MASTERS = "prescription_masters"
COL_ORDER_LINES = "order_lines"
COL_SPECIAL_NOTES = "special_notes"
COL_NOTE_MENTIONS = "note_mentions"

# 엣지 컬렉션
EC_VISIT_DIAGNOSIS = "visit_has_diagnosis"
EC_VISIT_ORDER = "visit_has_order"
EC_ORDER_PRESCRIPTION = "order_refers_prescription"
EC_VISIT_NOTE = "visit_has_note"
EC_ORDER_DIAGNOSIS = "order_associated_diagnosis"
EC_NOTE_HAS_MENTION = "note_has_mention"
EC_DIAGNOSIS_HAS_MENTION = "diagnosis_has_mention"
EC_PRESCRIPTION_HAS_MENTION = "prescription_has_mention"


def _parse_spring_properties(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        out[k] = v
    return out


def load_config(*, database: str | None = None) -> dict[str, str | int]:
    props = _parse_spring_properties(SPRING_LOCAL)
    hosts = os.environ.get("ARANGO_HOSTS") or props.get("arangodb.hosts", "127.0.0.1:8529")
    if ":" in hosts:
        host, port_s = hosts.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = hosts, 8529
    host = os.environ.get("ARANGO_HOST", host)
    port = int(os.environ.get("ARANGO_PORT", str(port)))
    db_name = os.environ.get(
        "ARANGO_DATABASE", props.get("arangodb.database", "bitcomputer_graph")
    )
    if database is not None and str(database).strip():
        db_name = str(database).strip()
    return {
        "host": host,
        "port": port,
        "user": os.environ.get("ARANGO_USER", props.get("arangodb.user", "root")),
        "password": os.environ.get("ARANGO_PASSWORD", props.get("arangodb.password", "")),
        "database": db_name,
    }


def _normalize_cell(v):
    if pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if s == "True":
            return True
        if s == "False":
            return False
        return s
    if isinstance(v, (bool, int, float)):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    return v


def row_to_doc(row: dict, key_field: str) -> dict | None:
    key = row.get(key_field)
    if key is None or (isinstance(key, float) and pd.isna(key)):
        return None
    key_s = str(key).strip()
    if not key_s:
        return None
    doc: dict = {"_key": key_s}
    for k, v in row.items():
        if k == key_field:
            continue
        nv = _normalize_cell(v)
        if nv is not None:
            doc[k] = nv
    return doc


def dataframe_to_docs(df: pd.DataFrame, key_field: str) -> list[dict]:
    records = df.to_dict("records")
    docs: list[dict] = []
    for r in records:
        d = row_to_doc(r, key_field)
        if d:
            docs.append(d)
    return docs


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def read_csv_bool_columns(path: Path, bool_cols: set[str]) -> pd.DataFrame:
    df = read_csv(path)
    for c in bool_cols:
        if c in df.columns:
            df[c] = df[c].map(lambda x: x == "True" if x in ("True", "False") else x)
    return df


def ensure_collection(db, name: str, *, edge: bool) -> None:
    if not db.has_collection(name):
        db.create_collection(name, edge=edge)


def chunked(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def insert_docs(coll, docs: list[dict], batch: int) -> None:
    for part in chunked(docs, batch):
        if not part:
            continue
        coll.insert_many(part, overwrite=True)


def _edge_key(from_coll: str, a: str, to_coll: str, b: str) -> str:
    raw = f"{from_coll}/{a}->{to_coll}/{b}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:26]


def edges_from_pairs(
    df: pd.DataFrame,
    from_col: str,
    to_col: str,
    from_coll: str,
    to_coll: str,
) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in df.to_dict("records"):
        a = r.get(from_col)
        b = r.get(to_col)
        if not a or not b or (isinstance(a, float) and pd.isna(a)):
            continue
        a, b = str(a).strip(), str(b).strip()
        if not b:
            continue
        pair = (a, b)
        if pair in seen:
            continue
        seen.add(pair)
        out.append(
            {
                "_key": _edge_key(from_coll, a, to_coll, b),
                "_from": f"{from_coll}/{a}",
                "_to": f"{to_coll}/{b}",
            }
        )
    return out


def edges_from_enriched_pairs(
    df: pd.DataFrame,
    from_col: str,
    to_col: str,
    from_coll: str,
    to_coll: str,
) -> list[dict]:
    """엣지 문서에 link_source, confidence, review_flag 등 부가 속성을 실어 넣는다."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in df.to_dict("records"):
        a = r.get(from_col)
        b = r.get(to_col)
        if not a or not b or (isinstance(a, float) and pd.isna(a)):
            continue
        a, b = str(a).strip(), str(b).strip()
        if not b:
            continue
        pair = (a, b)
        if pair in seen:
            continue
        seen.add(pair)
        doc: dict = {
            "_key": _edge_key(from_coll, a, to_coll, b),
            "_from": f"{from_coll}/{a}",
            "_to": f"{to_coll}/{b}",
        }
        ls = r.get("link_source")
        if ls is not None and str(ls).strip() != "":
            doc["link_source"] = str(ls).strip()
        conf = r.get("confidence")
        if conf is not None and str(conf).strip() != "":
            try:
                doc["confidence"] = float(conf)
            except (TypeError, ValueError):
                pass
        rf = r.get("review_flag")
        if rf is True or rf == "True" or rf == "true":
            doc["review_flag"] = True
        elif rf is False or rf == "False" or rf == "false":
            doc["review_flag"] = False
        out.append(doc)
    return out


def run_import(
    output_dir: Path,
    *,
    truncate: bool,
    batch: int,
    dry_run: bool,
    database: str | None = None,
) -> None:
    files = {
        "visit": output_dir / "01_visit_nodes.csv",
        "diagnosis": output_dir / "02_diagnosis_nodes.csv",
        "rx": output_dir / "03_prescription_master_nodes.csv",
        "order": output_dir / "04_order_line_nodes.csv",
        "note": output_dir / "05_special_note_nodes.csv",
        "e11": output_dir / "11_rel_visit_has_diagnosis.csv",
        "e12": output_dir / "12_rel_visit_has_order.csv",
        "e13": output_dir / "13_rel_order_refers_to_prescription.csv",
        "e14": output_dir / "14_rel_visit_has_note.csv",
        "e15": output_dir / "15_rel_order_associated_with_diagnosis.csv",
        "mention": output_dir / "06_note_mention_nodes.csv",
        "e16": output_dir / "16_rel_note_has_mention.csv",
        "e17": output_dir / "17_rel_diagnosis_has_mention.csv",
        "e18": output_dir / "18_rel_prescription_has_mention.csv",
    }
    files_required = {k: v for k, v in files.items() if k not in ("mention", "e16", "e17", "e18")}
    missing = [str(p) for p in files_required.values() if not p.is_file()]
    if missing:
        print("CSV 파일이 없습니다:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(database=database)
    print(f"출력 디렉터리: {output_dir}")
    print(
        f"Arango 대상: {cfg['host']}:{cfg['port']} / DB={cfg['database']} / user={cfg['user']}"
    )

    df_visit = read_csv(files["visit"])
    df_dx = read_csv(files["diagnosis"])
    df_rx = read_csv_bool_columns(files["rx"], {"review_flag"})
    df_order = read_csv_bool_columns(files["order"], {"raw_name_conflict_flag"})
    df_note = read_csv(files["note"])
    df_e11 = read_csv(files["e11"])
    df_e12 = read_csv(files["e12"])
    df_e13 = read_csv(files["e13"])
    df_e14 = read_csv(files["e14"])
    df_e15 = read_csv(files["e15"])
    df_mention = read_csv(files["mention"]) if files["mention"].is_file() else None
    if df_mention is not None and "is_abbreviation" in df_mention.columns:
        df_mention = read_csv_bool_columns(files["mention"], {"is_abbreviation"})
    df_e16 = read_csv(files["e16"]) if files["e16"].is_file() else None
    df_e17 = read_csv(files["e17"]) if files["e17"].is_file() else None
    df_e18 = read_csv(files["e18"]) if files["e18"].is_file() else None

    docs_visit = dataframe_to_docs(df_visit, "visit_id")
    docs_dx = dataframe_to_docs(df_dx, "diagnosis_code")
    docs_rx = dataframe_to_docs(df_rx, "prescription_code")
    docs_order = dataframe_to_docs(df_order, "order_line_id")
    docs_note = dataframe_to_docs(df_note, "note_id")
    docs_mention = (
        dataframe_to_docs(df_mention, "mention_id") if df_mention is not None else []
    )

    edges_11 = edges_from_pairs(df_e11, "visit_id", "diagnosis_code", COL_VISITS, COL_DIAGNOSES)
    edges_12 = edges_from_pairs(df_e12, "visit_id", "order_line_id", COL_VISITS, COL_ORDER_LINES)
    edges_13 = edges_from_pairs(
        df_e13, "order_line_id", "prescription_code", COL_ORDER_LINES, COL_PRESCRIPTION_MASTERS
    )
    edges_14 = edges_from_pairs(df_e14, "visit_id", "note_id", COL_VISITS, COL_SPECIAL_NOTES)
    edges_15 = edges_from_pairs(
        df_e15, "order_line_id", "diagnosis_code", COL_ORDER_LINES, COL_DIAGNOSES
    )
    edges_16 = (
        edges_from_pairs(
            df_e16, "note_id", "mention_id", COL_SPECIAL_NOTES, COL_NOTE_MENTIONS
        )
        if df_e16 is not None
        else []
    )
    edges_17 = (
        edges_from_enriched_pairs(
            df_e17, "diagnosis_code", "mention_id", COL_DIAGNOSES, COL_NOTE_MENTIONS
        )
        if df_e17 is not None and not df_e17.empty
        else []
    )
    edges_18 = (
        edges_from_enriched_pairs(
            df_e18, "prescription_code", "mention_id", COL_PRESCRIPTION_MASTERS, COL_NOTE_MENTIONS
        )
        if df_e18 is not None and not df_e18.empty
        else []
    )

    summary = [
        ("visits", len(docs_visit)),
        ("diagnoses", len(docs_dx)),
        ("prescription_masters", len(docs_rx)),
        ("order_lines", len(docs_order)),
        ("special_notes", len(docs_note)),
        (EC_VISIT_DIAGNOSIS, len(edges_11)),
        (EC_VISIT_ORDER, len(edges_12)),
        (EC_ORDER_PRESCRIPTION, len(edges_13)),
        (EC_VISIT_NOTE, len(edges_14)),
        (EC_ORDER_DIAGNOSIS, len(edges_15)),
        ("note_mentions", len(docs_mention)),
        (EC_NOTE_HAS_MENTION, len(edges_16)),
        (EC_DIAGNOSIS_HAS_MENTION, len(edges_17)),
        (EC_PRESCRIPTION_HAS_MENTION, len(edges_18)),
    ]
    print("적재 예정 건수:")
    for name, n in summary:
        print(f"  {name}: {n}")

    if dry_run:
        print("--dry-run 이므로 DB에 쓰지 않습니다.")
        return

    if ArangoClient is None:
        print("python-arango 가 설치되어 있지 않습니다. pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    client = ArangoClient(hosts=f"http://{cfg['host']}:{cfg['port']}")
    try:
        db = client.db(
            str(cfg["database"]),
            username=str(cfg["user"]),
            password=str(cfg["password"]),
        )
        db.properties()
    except ArangoError as e:
        print(f"ArangoDB 연결 실패: {e}", file=sys.stderr)
        print(
            "DB가 없으면 웹 UI나 arangosh에서 생성하거나, root 권한으로 생성한 뒤 다시 실행하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    doc_colls = [
        (COL_VISITS, False),
        (COL_DIAGNOSES, False),
        (COL_PRESCRIPTION_MASTERS, False),
        (COL_ORDER_LINES, False),
        (COL_SPECIAL_NOTES, False),
        (COL_NOTE_MENTIONS, False),
    ]
    edge_colls = [
        (EC_VISIT_DIAGNOSIS, True),
        (EC_VISIT_ORDER, True),
        (EC_ORDER_PRESCRIPTION, True),
        (EC_VISIT_NOTE, True),
        (EC_ORDER_DIAGNOSIS, True),
        (EC_NOTE_HAS_MENTION, True),
        (EC_DIAGNOSIS_HAS_MENTION, True),
        (EC_PRESCRIPTION_HAS_MENTION, True),
    ]

    for name, is_edge in doc_colls + edge_colls:
        ensure_collection(db, name, edge=is_edge)
    if truncate:
        for name, _ in doc_colls + edge_colls:
            db.collection(name).truncate()

    insert_docs(db.collection(COL_VISITS), docs_visit, batch)
    insert_docs(db.collection(COL_DIAGNOSES), docs_dx, batch)
    insert_docs(db.collection(COL_PRESCRIPTION_MASTERS), docs_rx, batch)
    insert_docs(db.collection(COL_ORDER_LINES), docs_order, batch)
    insert_docs(db.collection(COL_SPECIAL_NOTES), docs_note, batch)
    insert_docs(db.collection(COL_NOTE_MENTIONS), docs_mention, batch)

    insert_docs(db.collection(EC_VISIT_DIAGNOSIS), edges_11, batch)
    insert_docs(db.collection(EC_VISIT_ORDER), edges_12, batch)
    insert_docs(db.collection(EC_ORDER_PRESCRIPTION), edges_13, batch)
    insert_docs(db.collection(EC_VISIT_NOTE), edges_14, batch)
    insert_docs(db.collection(EC_ORDER_DIAGNOSIS), edges_15, batch)
    insert_docs(db.collection(EC_NOTE_HAS_MENTION), edges_16, batch)
    insert_docs(db.collection(EC_DIAGNOSIS_HAS_MENTION), edges_17, batch)
    insert_docs(db.collection(EC_PRESCRIPTION_HAS_MENTION), edges_18, batch)

    print("적재 완료.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Graph CSV → ArangoDB 적재")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="CSV가 있는 디렉터리 (기본: data_normalize/output)",
    )
    ap.add_argument(
        "--database",
        type=str,
        default=None,
        help="Arango DB 이름 (미지정 시 ARANGO_DATABASE / application-local.properties)",
    )
    ap.add_argument(
        "--append",
        action="store_true",
        help="컬렉션을 비우지 않음(문서·엣지는 _key로 덮어쓰기)",
    )
    ap.add_argument("--batch", type=int, default=1000, help="insert_many 배치 크기")
    ap.add_argument("--dry-run", action="store_true", help="DB 연결 없이 건수만 출력")
    args = ap.parse_args()

    run_import(
        args.output_dir.resolve(),
        truncate=not args.append,
        batch=args.batch,
        dry_run=args.dry_run,
        database=args.database,
    )


if __name__ == "__main__":
    main()
