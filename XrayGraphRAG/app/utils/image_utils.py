"""이미지 IO/전처리 유틸. PIL/NumPy만 의존."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Tuple, Union

import numpy as np
from PIL import Image


def load_grayscale(src: Union[str, Path, bytes]) -> Image.Image:
    if isinstance(src, (str, Path)):
        img = Image.open(str(src))
    else:
        img = Image.open(BytesIO(src))
    if img.mode != "L":
        img = img.convert("L")
    return img


def to_float01(img: Image.Image, size: int) -> np.ndarray:
    """[H, W] 0~1 float32. 비율 무시하고 강제 resize(기존 AI_BackEnd 정책과 동일)."""
    img_resized = img.resize((size, size), Image.LANCZOS)
    arr = np.asarray(img_resized, dtype=np.float32) / 255.0
    return arr


def save_array_as_png(arr: np.ndarray, path: Path) -> None:
    """0~1 float 또는 uint8 배열을 PNG로 저장."""
    a = arr
    if a.dtype != np.uint8:
        a = np.clip(a, 0.0, 1.0)
        a = (a * 255.0).astype(np.uint8)
    if a.ndim == 3 and a.shape[0] in (1, 3):
        a = np.transpose(a, (1, 2, 0))
        if a.shape[2] == 1:
            a = a[..., 0]
    Image.fromarray(a).save(str(path))


def normalize_minmax(arr: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    mn, mx = float(arr.min()), float(arr.max())
    if mx - mn < eps:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - mn) / (mx - mn)).astype(np.float32)


def split_left_right(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """[H, W] 마스크를 좌/우로 절반씩 분할. (좌측 = 영상 왼쪽 픽셀)."""
    h, w = mask.shape
    half = w // 2
    left = np.zeros_like(mask)
    right = np.zeros_like(mask)
    left[:, :half] = mask[:, :half]
    right[:, half:] = mask[:, half:]
    return left, right


def split_upper_lower(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    h, w = mask.shape
    half = h // 2
    upper = np.zeros_like(mask)
    lower = np.zeros_like(mask)
    upper[:half, :] = mask[:half, :]
    lower[half:, :] = mask[half:, :]
    return upper, lower
