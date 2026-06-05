"""시간 유틸. UTC ISO-8601 문자열을 표준으로 사용한다."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
