"""Storage 인터페이스(LocalStorage)는 추후 S3 어댑터 교체용 contract 이다.
case_service 가 현재는 `resolve()` 만 사용하지만, save_bytes/save_file 도 contract 의 일부이므로
회귀 테스트로 의도를 박아둔다. 이 테스트가 깨지면 backend 인터페이스가 바뀐 것이며 호출자도
함께 수정되어야 한다.
"""
from __future__ import annotations

from pathlib import Path

from app.services.storage_service import LocalStorage


def test_save_bytes_and_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")

    storage.save_bytes("a/hello.bin", b"\x00\x01")
    p = storage.resolve("a/hello.bin")
    assert p.exists() and p.read_bytes() == b"\x00\x01"

    src = tmp_path / "src.txt"
    src.write_text("hi", encoding="utf-8")
    storage.save_file("b/copy.txt", src)
    assert storage.resolve("b/copy.txt").read_text(encoding="utf-8") == "hi"
