"""ID 생성 유틸. case_key 형식: case_<8hex>."""
from __future__ import annotations

import secrets


def new_case_key() -> str:
    return f"case_{secrets.token_hex(4)}"


def safe_doc_key(name: str) -> str:
    """ArangoDB _key 허용 문자(영문, 숫자, _-:.@)만 남기고 정리."""
    return "".join(c for c in name if c.isalnum() or c in "_-.:@") or "_unknown"
