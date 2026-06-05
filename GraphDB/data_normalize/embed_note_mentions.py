#!/usr/bin/env python3
"""
note_mentions 컬렉션 문서에 텍스트 임베딩을 채웁니다 (Gemini embedding-001).

전제:
  - import_to_arango.py 로 note_mentions 가 적재됨
  - GOOGLE_API_KEY 설정 (또는 langchain_graph_qa/.env)

실행 (data_normalize):
  pip install langchain-google-genai python-dotenv
  python embed_note_mentions.py
  python embed_note_mentions.py --dry-run
  python embed_note_mentions.py --limit 50
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SPRING_LOCAL = REPO_ROOT / "Back-End" / "src" / "main" / "resources" / "application-local.properties"

try:
    from arango import ArangoClient
    from arango.exceptions import ArangoError
except ImportError:
    ArangoClient = None  # type: ignore

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except ImportError:
    GoogleGenerativeAIEmbeddings = None


def _parse_spring_properties(path: Path) -> dict[str, str]:
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


def load_dotenv_langchain() -> None:
    if not load_dotenv:
        return
    for p in (SCRIPT_DIR / ".env", REPO_ROOT / "GraphDB" / "langchain_graph_qa" / ".env"):
        if p.is_file():
            load_dotenv(p)
            return


def main() -> None:
    ap = argparse.ArgumentParser(description="note_mentions 에 embedding 필드 채우기")
    ap.add_argument("--model", default="models/embedding-001", help="Gemini embedding 모델")
    ap.add_argument("--batch", type=int, default=32, help="배치 크기")
    ap.add_argument("--limit", type=int, default=0, help="처리 최대 건수 (0=전체)")
    ap.add_argument("--dry-run", action="store_true", help="DB·API 호출 없이 건만 센다")
    args = ap.parse_args()

    load_dotenv_langchain()
    if not args.dry_run and not os.environ.get("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY 가 없습니다.", file=sys.stderr)
        raise SystemExit(1)
    if GoogleGenerativeAIEmbeddings is None:
        print("langchain-google-genai 가 필요합니다: pip install langchain-google-genai", file=sys.stderr)
        raise SystemExit(1)
    if ArangoClient is None:
        print("python-arango 가 필요합니다.", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_arango_config()
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
        print(f"Arango 연결 실패: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    coll = db.collection("note_mentions")
    aql = """
    FOR m IN note_mentions
      FILTER m.text != null AND LENGTH(TRIM(m.text)) > 0
      FILTER m.embedding == null OR LENGTH(m.embedding) == 0
      LIMIT @lim
      RETURN { _key: m._key, text: m.text }
    """
    lim = args.limit if args.limit > 0 else 1000000
    rows = list(db.aql.execute(aql, bind_vars={"lim": lim}))
    print(f"임베딩 대상: {len(rows)} 건 (dry_run={args.dry_run})")
    if args.dry_run:
        return

    embedder = GoogleGenerativeAIEmbeddings(model=args.model)
    updated = 0
    batch: list[str] = []
    batch_keys: list[str] = []

    def flush() -> None:
        nonlocal updated, batch, batch_keys
        if not batch:
            return
        vectors = embedder.embed_documents(batch)
        for k, vec in zip(batch_keys, vectors):
            db.collection("note_mentions").update({"_key": k, "embedding": vec, "embedding_model": args.model})
            updated += 1
        batch = []
        batch_keys = []

    for r in rows:
        batch.append(r["text"][:8000])
        batch_keys.append(r["_key"])
        if len(batch) >= args.batch:
            flush()
    flush()
    print(f"업데이트 완료: {updated} 건")


if __name__ == "__main__":
    main()
