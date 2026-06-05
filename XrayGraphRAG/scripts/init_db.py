"""ArangoDB 컬렉션 / 그래프 / 벡터 인덱스 / seed 초기화.

`POST /admin/init-db`와 동일한 동작을 HTTP 없이 직접 수행한다.

실행:
  python scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def _setup() -> None:
    for s in ("stdout", "stderr"):
        try:
            getattr(sys, s).reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    here = Path(__file__).resolve()
    if str(here.parent.parent) not in sys.path:
        sys.path.insert(0, str(here.parent.parent))


_setup()

from app.config import get_settings  # noqa: E402
from app.db.arango_client import get_db  # noqa: E402
from app.db.schema import (  # noqa: E402
    ensure_collections,
    ensure_graph,
    ensure_vector_indexes,
    seed_defaults,
)


def main() -> int:
    settings = get_settings()
    print(f"[arango] {settings.ARANGO_URL} db={settings.ARANGO_DB_NAME}")
    db = get_db(settings)

    print("[init] ensure collections")
    ensure_collections(db)
    print("[init] ensure graph")
    ensure_graph(db, settings)
    print("[init] seed defaults (diseases / rois / findings / domain edges)")
    seed_defaults(db)
    print("[init] ensure vector indexes")
    res = ensure_vector_indexes(db, settings)
    print(f"[done] vector_supported={res['vector_supported']}")
    for d in res["details"]:
        print(f"   - {d}")
    return 0 if res["vector_supported"] else 0  # fallback도 OK


if __name__ == "__main__":
    raise SystemExit(main())
