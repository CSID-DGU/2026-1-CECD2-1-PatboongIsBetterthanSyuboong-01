"""artifact 저장 추상화. 로컬 FS 구현 + S3 교체용 인터페이스."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol, Union


class StorageBackend(Protocol):
    def save_bytes(self, key: str, data: bytes) -> str:  # pragma: no cover
        ...

    def save_file(self, key: str, src_path: Path) -> str:  # pragma: no cover
        ...

    def resolve(self, key: str) -> Path:  # pragma: no cover
        ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_bytes(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.write_bytes(data)
        return str(p.relative_to(self.root.parent)) if self.root.parent in p.parents else str(p)

    def save_file(self, key: str, src_path: Path) -> str:
        p = self._path(key)
        if Path(src_path) != p:
            shutil.copyfile(str(src_path), str(p))
        return str(p)

    def resolve(self, key: str) -> Path:
        return self._path(key)
