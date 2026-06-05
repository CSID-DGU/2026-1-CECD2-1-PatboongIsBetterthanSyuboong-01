"""상병코드.csv → disease 테이블 일괄 적재"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent

BATCH_SIZE = 400


def sql_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "''").replace("\x00", "") + "'"


def iter_disease_rows(csv_path: Path) -> Iterator[tuple[str, str, str | None]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(header) < 3:
            raise SystemExit(f"CSV 헤더가 올바르지 않습니다: {header!r}")

        for row in reader:
            if len(row) < 3:
                continue
            code = row[0].strip()
            name = row[1].strip()
            name_en_raw = row[2].strip()
            if not code or not name:
                continue
            if not name_en_raw or name_en_raw == "0":
                name_en: str | None = None
            else:
                name_en = name_en_raw
            yield (code, name, name_en)


def _hint_access_denied() -> None:
    print(
        "→ MySQL 1045: 비밀번호/포트가 서버와 다릅니다.\n"
        "  Docker: MYSQL_PASSWORD='compose.yaml의 MYSQL_ROOT_PASSWORD' MYSQL_PORT=3307\n"
        "  로컬 MySQL: MYSQL_PORT=3306 MYSQL_PASSWORD=...\n"
        "  root@192.168.65.1 은 호스트→Docker 접속 시 정상적으로 보이는 클라이언트 주소입니다.",
        file=sys.stderr,
    )


def build_insert_sql(batch: list[tuple[str, str, str | None]]) -> str:
    parts: list[str] = []
    for code, name, name_en in batch:
        ne = "NULL" if name_en is None else sql_str(name_en)
        parts.append(f"({sql_str(code)},{sql_str(name)},{ne})")
    return "INSERT INTO disease (code, name, name_en) VALUES " + ",".join(parts) + ";"


def main() -> None:
    csv_path = Path(os.environ.get("DISEASE_CSV", BACKEND_ROOT / "상병코드.csv")).resolve()
    if not csv_path.is_file():
        print(f"CSV 없음: {csv_path}", file=sys.stderr)
        sys.exit(1)

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3307")
    user = os.environ.get("MYSQL_USER", "root")
    # compose.yaml MYSQL_ROOT_PASSWORD 와 동기화 (application.properties 5776 은 로컬 전용일 수 있음)
    password = os.environ.get("MYSQL_PASSWORD", "Dd905925@")
    database = os.environ.get("MYSQL_DATABASE", "bitcomputer")

    cnf_path: str | None = None
    try:
        cnf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".cnf")
        cnf.write(
            f"""[client]
host={host}
port={port}
user={user}
password={password}
"""
        )
        cnf.flush()
        cnf_path = cnf.name
        cnf.close()

        create_sql = """SET NAMES utf8mb4;
CREATE TABLE IF NOT EXISTS disease (
  id INT NOT NULL AUTO_INCREMENT,
  code VARCHAR(128) NOT NULL,
  name TEXT NOT NULL,
  name_en TEXT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
        r0 = subprocess.run(
            ["mysql", f"--defaults-extra-file={cnf_path}", database, "-e", create_sql],
            capture_output=True,
            text=True,
        )
        if r0.returncode != 0:
            err = r0.stderr or r0.stdout
            print(err, file=sys.stderr)
            if "1045" in err:
                _hint_access_denied()
            sys.exit(r0.returncode)

        # JPA 등으로 예전에 만든 disease 테이블에는 name_en 이 없을 수 있음 (CREATE IF NOT EXISTS 는 스키마 갱신 안 함)
        r_alter = subprocess.run(
            [
                "mysql",
                f"--defaults-extra-file={cnf_path}",
                database,
                "-e",
                "ALTER TABLE disease ADD COLUMN name_en TEXT NULL;",
            ],
            capture_output=True,
            text=True,
        )
        if r_alter.returncode != 0:
            err_a = r_alter.stderr or r_alter.stdout
            if "1060" not in err_a and "Duplicate column" not in err_a:
                print(err_a, file=sys.stderr)
                if "1045" in err_a:
                    _hint_access_denied()
                sys.exit(r_alter.returncode)

        purge_sql = """SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM disease;
ALTER TABLE disease AUTO_INCREMENT = 1;
SET FOREIGN_KEY_CHECKS = 1;
"""
        r0 = subprocess.run(
            ["mysql", f"--defaults-extra-file={cnf_path}", database, "-e", purge_sql],
            capture_output=True,
            text=True,
        )
        if r0.returncode != 0:
            err = r0.stderr or r0.stdout
            print(err, file=sys.stderr)
            if "1045" in err:
                _hint_access_denied()
            sys.exit(r0.returncode)

        total = 0
        batch: list[tuple[str, str, str | None]] = []
        for row in iter_disease_rows(csv_path):
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                sql = build_insert_sql(batch)
                r = subprocess.run(
                    ["mysql", f"--defaults-extra-file={cnf_path}", database, "-e", sql],
                    capture_output=True,
                    text=True,
                )
                if r.returncode != 0:
                    err = r.stderr or r.stdout
                    print(err, file=sys.stderr)
                    if "1045" in err:
                        _hint_access_denied()
                    sys.exit(r.returncode)
                total += len(batch)
                batch = []
        if batch:
            sql = build_insert_sql(batch)
            r = subprocess.run(
                ["mysql", f"--defaults-extra-file={cnf_path}", database, "-e", sql],
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                err = r.stderr or r.stdout
                print(err, file=sys.stderr)
                if "1045" in err:
                    _hint_access_denied()
                sys.exit(r.returncode)
            total += len(batch)

        print(f"적재 완료: {total}행 ({csv_path.name})")

        r2 = subprocess.run(
            [
                "mysql",
                f"--defaults-extra-file={cnf_path}",
                database,
                "-e",
                "SELECT COUNT(*) AS disease_rows FROM disease;",
            ],
            capture_output=True,
            text=True,
        )
        if r2.returncode == 0:
            print(r2.stdout.strip())
    finally:
        if cnf_path:
            Path(cnf_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
