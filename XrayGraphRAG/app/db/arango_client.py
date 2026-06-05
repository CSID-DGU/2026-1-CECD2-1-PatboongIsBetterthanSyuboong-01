"""ArangoDB 연결 헬퍼.

python-arango (`pip install python-arango`) 사용. 인증/DB 보장 로직 포함.
"""
from __future__ import annotations

from typing import Optional

from arango import ArangoClient
from arango.database import StandardDatabase

from app.config import Settings


_client: Optional[ArangoClient] = None
_db: Optional[StandardDatabase] = None


def get_client(settings: Settings) -> ArangoClient:
    global _client
    if _client is None:
        _client = ArangoClient(hosts=settings.ARANGO_URL)
    return _client


def get_db(settings: Settings) -> StandardDatabase:
    global _db
    if _db is not None:
        return _db
    client = get_client(settings)
    sys_db = client.db("_system", username=settings.ARANGO_USERNAME, password=settings.ARANGO_PASSWORD)
    if not sys_db.has_database(settings.ARANGO_DB_NAME):
        sys_db.create_database(settings.ARANGO_DB_NAME)
    _db = client.db(
        settings.ARANGO_DB_NAME,
        username=settings.ARANGO_USERNAME,
        password=settings.ARANGO_PASSWORD,
    )
    return _db


def reset_db_singleton() -> None:
    """테스트에서 사용."""
    global _client, _db
    _client = None
    _db = None
