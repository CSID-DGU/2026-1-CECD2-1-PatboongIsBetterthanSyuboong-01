"""
전역 설정. 환경 변수에서 읽되, 모든 키에 합리적인 기본값을 둔다.

설계 메모:
- 본 시스템은 분류 모델을 쓰지 않고 reconstruction error embedding으로 case retrieval을 한다.
- mock-first: 환경에 모델 파일이 없어도 end-to-end 동작을 보장한다.
- 실제 PyTorch 모델 연결은 USE_TORCH_ANOMALY=true 등으로 토글한다.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

# 프로젝트 루트의 .env 를 가능한 한 빨리 로드한다.
# - OS 환경변수가 이미 설정돼 있으면 그쪽이 우선 (override=False).
#   → Docker compose 가 ARANGO_PASSWORD 등을 직접 주입한 컨테이너 환경에서는
#     컨테이너 환경변수가 그대로 유지된다.
# - python-dotenv 가 미설치된 환경(예: 최소 의존만 설치된 컨테이너)에서도
#   ImportError 로 죽지 않도록 안전하게 무시한다.
try:
    from dotenv import load_dotenv  # type: ignore

    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    for _candidate in (_PROJECT_ROOT / ".env", _PROJECT_ROOT / "XrayGraphRAG" / ".env"):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except Exception:
    pass


def _bool(v: Optional[str], default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _int(v: Optional[str], default: int) -> int:
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def _float(v: Optional[str], default: float) -> float:
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default


class Settings:
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    APP_ROOT: Path = Path(__file__).resolve().parent

    # ArangoDB
    ARANGO_URL: str = os.environ.get("ARANGO_URL", "http://localhost:8529")
    ARANGO_DB_NAME: str = os.environ.get("ARANGO_DB_NAME", "xray_graph_db")
    ARANGO_USERNAME: str = os.environ.get("ARANGO_USERNAME", "root")
    ARANGO_PASSWORD: str = os.environ.get("ARANGO_PASSWORD", "password")
    ARANGO_GRAPH_NAME: str = os.environ.get("ARANGO_GRAPH_NAME", "xray_graph")

    # Vector index. ArangoDB 3.12+에서 vector type 인덱스 지원.
    EMBEDDING_DIM: int = _int(os.environ.get("EMBEDDING_DIM"), 768)
    VECTOR_METRIC: str = os.environ.get("VECTOR_METRIC", "cosine")
    VECTOR_NLISTS: int = _int(os.environ.get("VECTOR_NLISTS"), 100)
    VECTOR_NPROBE: int = _int(os.environ.get("VECTOR_NPROBE"), 20)
    VECTOR_TRAINING_ITERS: int = _int(os.environ.get("VECTOR_TRAINING_ITERS"), 25)

    # Storage
    STORAGE_DIR: Path = Path(os.environ.get("STORAGE_DIR", str(PROJECT_ROOT / "XrayGraphRAG" / "storage")))

    # Image processing
    IMAGE_SIZE: int = _int(os.environ.get("IMAGE_SIZE"), 256)

    # Model versioning(같은 modelVersion / maskVersion끼리만 비교하도록 필터에 사용)
    MODEL_VERSION: str = os.environ.get("MODEL_VERSION", "ae_squid_v1")
    MASK_VERSION: str = os.environ.get("MASK_VERSION", "lung_heart_mask_v1")
    EMBEDDING_VERSION: str = os.environ.get("EMBEDDING_VERSION", "mock_pca_v1")

    # ML toggles
    USE_TORCH_ANOMALY: bool = _bool(os.environ.get("USE_TORCH_ANOMALY"), False)
    USE_TORCH_ROI: bool = _bool(os.environ.get("USE_TORCH_ROI"), False)
    USE_TORCH_EMBEDDING: bool = _bool(os.environ.get("USE_TORCH_EMBEDDING"), False)

    # 기존 AI_BackEnd의 SQUID 모델 폴더(존재하면 torch adapter에서 사용)
    SQUID_MODEL_DIR: Path = Path(
        os.environ.get(
            "SQUID_MODEL_DIR",
            str(PROJECT_ROOT / "AI_BackEnd" / "squid_exp1_256_mask"),
        )
    )

    # Retrieval
    DEFAULT_TOP_K: int = _int(os.environ.get("DEFAULT_TOP_K"), 20)

    # Severity thresholds (p95 기준)
    SEVERITY_HIGH_P95: float = _float(os.environ.get("SEVERITY_HIGH_P95"), 0.25)
    SEVERITY_HIGH_AREA: float = _float(os.environ.get("SEVERITY_HIGH_AREA"), 0.20)
    SEVERITY_MEDIUM_P95: float = _float(os.environ.get("SEVERITY_MEDIUM_P95"), 0.12)

    # Uncertainty thresholds
    UNCERT_HIGH_TOP1: float = _float(os.environ.get("UNCERT_HIGH_TOP1"), 0.65)
    UNCERT_MED_GAP: float = _float(os.environ.get("UNCERT_MED_GAP"), 0.10)
    UNCERT_MIN_CASES: int = _int(os.environ.get("UNCERT_MIN_CASES"), 8)

    # Safety文구
    SAFETY_NOTICE: str = (
        "이 결과는 의학적 진단이 아닙니다. "
        "유사 reconstruction error pattern 기반의 후보 추론이며, "
        "최종 판독 및 진단은 반드시 영상의학 전문의가 수행해야 합니다."
    )

    @property
    def images_dir(self) -> Path:
        return self.STORAGE_DIR / "images"

    @property
    def recon_dir(self) -> Path:
        return self.STORAGE_DIR / "recon"

    @property
    def heatmap_dir(self) -> Path:
        return self.STORAGE_DIR / "heatmaps"

    def ensure_storage(self) -> None:
        for p in (self.images_dir, self.recon_dir, self.heatmap_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_storage()
    return s
