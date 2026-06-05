r"""kagglehub 으로 CheXpert v1.0(small) 데이터셋을 받아 원하는 경로로 정리한다.

사용 예:
  pip install kagglehub
  python scripts/download_chexpert.py                                # 캐시에 받고 archive 경로만 출력
  python scripts/download_chexpert.py --dest D:\data\chexpert        # dest 로 정리 (기본: junction[win]/symlink[posix])
  python scripts/download_chexpert.py --dest .\archive --mode copy   # 실제 복사 (디스크 사용량 큼)

이후 진행:
  python scripts/init_db.py
  python scripts/seed_chexpert.py --archive <dest> --split valid --frontal-only

비고
- kagglehub 캐시는 기본적으로 ~/.cache/kagglehub/datasets/ashery/chexpert/versions/N/ 에 저장된다.
- seed_chexpert.py 는 <archive>/valid.csv, <archive>/valid/... 구조를 요구하므로 이 스크립트가
  캐시 안의 실제 dataset 루트를 자동 감지해 dest 로 가져온다.
- --mode junction (Windows 기본) / --mode symlink (POSIX 기본) 은 디스크를 추가로 사용하지 않는다.
- --mode copy 는 약 11GB 이상의 추가 공간이 필요하다 (CheXpert-v1.0-small 기준).

요구 사항
- Kaggle 인증이 필요하다. 처음 실행 시 kagglehub 가 자동으로 브라우저 또는 ~/.kaggle/kaggle.json
  토큰을 통해 인증한다. 토큰 파일 위치/생성 방법은 Kaggle 계정 페이지(Account -> Create New API Token)
  를 참고한다.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _setup_io() -> None:
    for s in ("stdout", "stderr"):
        try:
            getattr(sys, s).reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_setup_io()

DATASET_HANDLE = "ashery/chexpert"


def _detect_inner_root(downloaded: Path) -> Path:
    """다운로드 디렉토리에서 valid.csv / train.csv 가 위치한 실제 루트를 찾는다."""
    candidates = [
        downloaded,
        downloaded / "CheXpert-v1.0-small",
        downloaded / "CheXpert-v1.0",
        downloaded / "chexpert",
    ]
    for cand in candidates:
        if cand.is_dir() and ((cand / "valid.csv").exists() or (cand / "train.csv").exists()):
            return cand
    # 깊이 탐색
    for csv_path in downloaded.rglob("valid.csv"):
        return csv_path.parent
    for csv_path in downloaded.rglob("train.csv"):
        return csv_path.parent
    raise FileNotFoundError(
        f"valid.csv / train.csv 를 찾지 못했습니다. 다운로드 결과: {downloaded}"
    )


def _link_or_copy(src: Path, dst: Path, mode: str) -> None:
    """child 단위(루트 1단계)로 dst 에 가져온다."""
    if dst.exists() and not dst.is_dir():
        raise NotADirectoryError(f"dest must be a directory: {dst}")
    dst.mkdir(parents=True, exist_ok=True)

    for child in sorted(src.iterdir()):
        target = dst / child.name
        if target.exists():
            print(f"  [skip] already exists: {target.name}")
            continue
        if mode == "copy":
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
            print(f"  [copy ] {child.name}")
        elif mode == "symlink":
            target.symlink_to(child, target_is_directory=child.is_dir())
            print(f"  [link ] {child.name}")
        elif mode == "junction":
            if child.is_dir():
                # Windows directory junction: 권한 불필요
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(target), str(child)],
                    capture_output=True, text=True,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"mklink /J 실패: {completed.stderr.strip()}"
                    )
                print(f"  [junc ] {child.name}")
            else:
                # 파일은 hardlink 시도(같은 볼륨 한정), 실패 시 copy
                try:
                    os.link(child, target)
                    print(f"  [hlink] {child.name}")
                except OSError:
                    shutil.copy2(child, target)
                    print(f"  [copy ] {child.name} (hardlink 실패, copy)")
        else:
            raise ValueError(f"unknown mode: {mode}")


def _verify(dest: Path) -> bool:
    has_valid = (dest / "valid.csv").exists()
    has_train = (dest / "train.csv").exists()
    has_valid_dir = (dest / "valid").is_dir()
    has_train_dir = (dest / "train").is_dir()
    print("[verify]")
    print(f"  valid.csv : {has_valid}")
    print(f"  train.csv : {has_train}")
    print(f"  valid/    : {has_valid_dir}")
    print(f"  train/    : {has_train_dir}")
    return has_valid or has_train


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest", type=str, default=None,
        help="archive 정리 경로. 미지정 시 kagglehub 캐시 경로를 그대로 archive 로 사용한다.",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "symlink", "junction"],
        default=None,
        help="--dest 사용 시 가져오기 방식. 기본: Windows=junction, POSIX=symlink",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="dest 가 비어있지 않아도 진행 (이름 중복은 항상 skip)",
    )
    parser.add_argument(
        "--cache-dir", type=str, default=None,
        help="KAGGLEHUB_CACHE 를 임시로 이 경로로 설정한 뒤 다운로드",
    )
    args = parser.parse_args()

    if args.cache_dir:
        cache_dir = str(Path(args.cache_dir).resolve())
        os.environ["KAGGLEHUB_CACHE"] = cache_dir
        print(f"[cfg] KAGGLEHUB_CACHE={cache_dir}")

    try:
        import kagglehub  # type: ignore
    except ImportError:
        print("[fail] kagglehub 가 설치되어 있지 않습니다.\n"
              "       pip install kagglehub 또는 requirements.txt 의 주석 해제 후 재설치하세요.")
        return 2

    print(f"[download] kagglehub.dataset_download('{DATASET_HANDLE}')")
    raw_path = Path(kagglehub.dataset_download(DATASET_HANDLE))
    print(f"[download] cached at: {raw_path}")

    inner = _detect_inner_root(raw_path)
    print(f"[detect ] dataset root: {inner}")

    if args.dest is None:
        print()
        print("[done] --dest 미지정. 아래 경로를 그대로 --archive 로 사용하세요:")
        print(f"  python scripts/seed_chexpert.py --archive \"{inner}\" --split valid --frontal-only")
        return 0

    dest = Path(args.dest).resolve()
    if dest.exists() and any(dest.iterdir()) and not args.force:
        print(f"[fail] dest 가 이미 존재하고 비어있지 않습니다: {dest}")
        print("       기존 내용을 보존한 채 진행하려면 --force 를 추가하세요 (이름 중복은 자동 skip).")
        return 2

    mode = args.mode or ("junction" if os.name == "nt" else "symlink")
    print(f"[bring  ] mode={mode}  {inner} -> {dest}")
    _link_or_copy(inner, dest, mode)

    ok = _verify(dest)
    if not ok:
        print("[warn ] valid.csv / train.csv 둘 다 미발견. 데이터셋 구조를 확인하세요.")
        return 3

    print()
    print("[done] 다음 명령으로 등록을 진행하세요:")
    print("  python scripts/init_db.py")
    print(f"  python scripts/seed_chexpert.py --archive \"{dest}\" --split valid --frontal-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
