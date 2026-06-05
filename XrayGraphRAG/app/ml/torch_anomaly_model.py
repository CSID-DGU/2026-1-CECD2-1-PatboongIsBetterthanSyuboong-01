"""실제 SQUID 모델(AI_BackEnd/squid_exp1_256_mask) 어댑터.

USE_TORCH_ANOMALY=true 일 때 사용. torch / 모델 가중치가 없으면 build factory에서
mock으로 fallback 한다.

전제조건(데이터):
  AI_BackEnd/squid_exp1_256_mask/
    config.py
    squid.py
    discriminator.py
    model.pth                (학습된 가중치)
    discriminator.pth        (학습된 가중치)
    visualizations/<run>/model_config.txt   (mean/std/threshold; 없으면 기본값)

입력:
  reconstruct(image: np.ndarray)
    - image shape: (H, W) grayscale, dtype float32, range [0, 1]
    - 모델은 256x256을 기대하므로 호출자가 사전에 resize(=preprocessing_service)를 끝내야 한다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np


class TorchSquidAnomalyModel:
    EXPECTED_HW = 256

    def __init__(self, model_dir: Path) -> None:
        import torch

        # 일부 환경(Windows cp949 콘솔)에서 SQUID 코드 내부 print()의 유니코드(⚠/✅)가
        # UnicodeEncodeError 를 일으키므로 안전망으로 stdout/stderr 를 utf-8 로 재설정.
        for stream_name in ("stdout", "stderr"):
            s = getattr(sys, stream_name, None)
            if s is None:
                continue
            try:  # pragma: no cover
                s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        if not model_dir.exists():
            raise FileNotFoundError(f"SQUID model dir not found: {model_dir}")

        ai_root = model_dir.parent
        # AI_BackEnd 패키지(`configs/`, `models/`, `model_loader.py`) 우선 인식.
        # 주의: squid_exp1_256_mask 자체는 sys.path에 추가하지 않는다.
        # 그 폴더에도 `config.py`가 있어 model_loader 의 `from config import MODEL_DIR`가
        # 잘못된 모듈로 분기될 수 있기 때문이다. 폴더 내부 파일들은 AnomalyDetector 가
        # importlib.util.spec_from_file_location 으로 직접 로드한다.
        self._ensure_path(ai_root)

        # 같은 이름 충돌(`config`, `squid`, `discriminator`)을 막기 위해 캐시 정리.
        for k in ("config", "squid", "discriminator", "model_loader"):
            sys.modules.pop(k, None)

        # AI_BackEnd/config.py 를 명시적으로 `sys.modules['config']`에 박아두면,
        # model_loader 가 아무리 sys.path 우선순위를 바꿔 끼워 넣어도 `from config import MODEL_DIR`
        # 가 항상 AI_BackEnd 의 config 를 보게 된다.
        import importlib.util as _ilu

        ai_config_path = ai_root / "config.py"
        if not ai_config_path.exists():
            raise FileNotFoundError(f"AI_BackEnd/config.py not found: {ai_config_path}")
        spec = _ilu.spec_from_file_location("config", ai_config_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"failed to load spec for {ai_config_path}")
        mod = _ilu.module_from_spec(spec)
        sys.modules["config"] = mod
        spec.loader.exec_module(mod)

        from model_loader import AnomalyDetector  # type: ignore  # AI_BackEnd 위치

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.detector = AnomalyDetector(model_dir)
        self.detector.model.eval()

    @staticmethod
    def _ensure_path(p: Path) -> None:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)

    def reconstruct(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 2:
            raise ValueError(f"image must be [H,W], got shape {image.shape}")
        if image.shape != (self.EXPECTED_HW, self.EXPECTED_HW):
            raise ValueError(
                f"SQUID expects {self.EXPECTED_HW}x{self.EXPECTED_HW}, got {image.shape}. "
                "Did you set IMAGE_SIZE=256?"
            )

        torch = self._torch
        with torch.no_grad():
            t = (
                torch.from_numpy(np.ascontiguousarray(image, dtype=np.float32))
                .unsqueeze(0)
                .unsqueeze(0)
                .to(self.device)
            )
            out = self.detector.model(t)
            recon = out["recon"].detach().cpu().numpy()[0, 0]
        return np.clip(recon, 0.0, 1.0).astype(np.float32)


def build_torch_anomaly_model(model_dir: Path) -> Optional[TorchSquidAnomalyModel]:
    try:
        return TorchSquidAnomalyModel(model_dir)
    except Exception as e:  # pragma: no cover - 환경 의존
        print(f"[ml] torch anomaly model unavailable, falling back to mock: {e}")
        return None
