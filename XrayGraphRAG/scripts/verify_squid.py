"""실제 SQUID 어댑터 검증 스크립트.

목표:
  1) AI_BackEnd/squid_exp1_256_mask 의 model.pth/discriminator.pth 가중치를 로드해
     `TorchSquidAnomalyModel` 이 import + 초기화 가능한지 확인.
  2) (이미지 경로가 주어지면) preprocess → reconstruct → error map → ROI 통계 →
     heatmap 저장까지 end-to-end 동작을 검증.
  3) Mock pipeline과 결과를 비교해 reconstruction이 다른 분포를 내는지(blur 가 아닌지)
     수치로 확인.

실행 예:
  # 어댑터만 로드 가능한지 확인 (이미지 불필요)
  python scripts/verify_squid.py

  # 이미지로 끝까지 검증
  python scripts/verify_squid.py --image path/to/chest.png
  python scripts/verify_squid.py --image storage/test_inputs/chest.png

옵션:
  --image PATH     입력 X-ray 경로
  --out  DIR       결과 저장 폴더(기본: storage/verify/<timestamp>/)
  --use-mask       MockROIModel 로 좌/우 폐, 심장 ROI mask 적용
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np


def _setup_io_and_paths() -> None:
    # Windows 콘솔 cp949 환경에서 SQUID 코드의 print(⚠/✅)가 죽지 않도록 stdout/stderr UTF-8 재설정
    for stream_name in ("stdout", "stderr"):
        s = getattr(sys, stream_name, None)
        if s is None:
            continue
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    here = Path(__file__).resolve()
    project_root = here.parent.parent  # XrayGraphRAG/
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_setup_io_and_paths()

from app.config import get_settings  # noqa: E402
from app.ml.factory import build_models  # noqa: E402
from app.ml.mock_anomaly_model import MockAnomalyModel  # noqa: E402
from app.ml.mock_roi_model import MockROIModel  # noqa: E402
from app.ml.torch_anomaly_model import build_torch_anomaly_model  # noqa: E402
from app.services.error_map_service import (  # noqa: E402
    apply_roi_mask,
    compute_error_map,
    compute_roi_stats,
)
from app.services.heatmap_service import save_heatmap  # noqa: E402
from app.services.preprocessing_service import preprocess  # noqa: E402
from app.utils.image_utils import save_array_as_png  # noqa: E402


def _stats_summary(name: str, arr: np.ndarray) -> dict:
    return {
        "name": name,
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--use-mask", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    print(f"[settings] SQUID_MODEL_DIR={settings.SQUID_MODEL_DIR}")
    print(f"[settings] IMAGE_SIZE={settings.IMAGE_SIZE}")
    print(f"[settings] EMBEDDING_DIM={settings.EMBEDDING_DIM}")

    # ---------- 1) 어댑터 빌드 ----------
    t0 = time.time()
    model = build_torch_anomaly_model(settings.SQUID_MODEL_DIR)
    if model is None:
        print("[FAIL] TorchSquidAnomalyModel build failed. Falling back path triggered.")
        print("       --> AI_BackEnd/squid_exp1_256_mask 에 model.pth / discriminator.pth /")
        print("           config.py / squid.py / discriminator.py 가 모두 존재하는지 확인하세요.")
        return 2
    dt = time.time() - t0
    print(f"[OK] SQUID adapter built in {dt:.2f}s on device={model.device}")
    print(f"     threshold={getattr(model.detector, 'threshold', None)}")
    print(f"     mean={getattr(model.detector, 'mean', None)} "
          f"std={getattr(model.detector, 'std', None)}")

    if args.image is None:
        print("[INFO] --image 가 주어지지 않아 forward 검증은 생략합니다.")
        print("       이미지로 끝까지 검증하려면:")
        print("         python scripts/verify_squid.py --image path/to/chest.png")
        return 0

    # ---------- 2) 이미지 forward ----------
    img_path = Path(args.image)
    if not img_path.exists():
        print(f"[FAIL] image not found: {img_path}")
        return 3

    out_dir = Path(args.out) if args.out else (settings.STORAGE_DIR / "verify" / time.strftime("%Y%m%d_%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)

    image = preprocess(img_path.read_bytes(), settings.IMAGE_SIZE)
    print("[step] preprocess:", _stats_summary("image", image))

    t0 = time.time()
    recon = model.reconstruct(image)
    print(f"[step] SQUID reconstruct: {time.time() - t0:.3f}s",
          _stats_summary("recon", recon))

    error_map = compute_error_map(image, recon)
    print("[step] error_map:", _stats_summary("error_map", error_map))

    masks: Optional[dict] = None
    if args.use_mask:
        masks = MockROIModel().generate_masks(image)
        print("[step] mock ROI masks:", {k: int(v.sum()) for k, v in masks.items()})

    if masks:
        roi_stats = compute_roi_stats(error_map, masks, settings)
        compact = {k: {
            "mean": round(v.meanError, 4),
            "p95": round(v.p95Error, 4),
            "max": round(v.maxError, 4),
            "areaRatio": round(v.areaRatio, 4),
            "severity": v.severity,
        } for k, v in roi_stats.items()}
        print("[step] ROI stats:")
        print(json.dumps(compact, indent=2, ensure_ascii=False))

    # ---------- 3) Mock pipeline 비교 ----------
    mock_model = MockAnomalyModel()
    mock_recon = mock_model.reconstruct(image)
    mock_err = compute_error_map(image, mock_recon)
    diff_pix = float(np.mean(np.abs(recon - mock_recon)))
    diff_err = float(np.mean(np.abs(error_map - mock_err)))
    print(f"[compare] mean|squid_recon - mock_recon| = {diff_pix:.4f}")
    print(f"[compare] mean|squid_err   - mock_err  | = {diff_err:.4f}")
    if diff_pix < 1e-4:
        print("[WARN] SQUID recon이 mock(blur)과 거의 동일합니다. 가중치가 untrained "
              "이거나 forward path가 의심됩니다.")
    elif diff_err < 1e-4:
        print("[WARN] error_map이 mock과 거의 동일합니다.")

    # ---------- 4) 산출물 저장 ----------
    save_array_as_png(image, out_dir / "01_input.png")
    save_array_as_png(recon, out_dir / "02_recon.png")
    save_array_as_png(error_map, out_dir / "03_error_map.png")
    save_heatmap(error_map, out_dir / "04_heatmap.png", original=image, alpha=0.55)
    save_array_as_png(mock_recon, out_dir / "10_mock_recon.png")
    save_array_as_png(mock_err, out_dir / "11_mock_error.png")

    print(f"[OK] saved artifacts to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
