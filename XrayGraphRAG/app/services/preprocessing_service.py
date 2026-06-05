"""이미지 전처리: load -> grayscale -> resize -> 0~1 float."""
from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np

from app.utils.image_utils import load_grayscale, to_float01


def preprocess(src: Union[str, Path, bytes], image_size: int) -> np.ndarray:
    img = load_grayscale(src)
    return to_float01(img, image_size)
