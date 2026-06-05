import numpy as np

from app.services.error_map_service import apply_roi_mask, compute_error_map


def test_compute_error_map_zero_when_identical():
    img = np.full((32, 32), 0.5, dtype=np.float32)
    err = compute_error_map(img, img)
    assert err.shape == img.shape
    assert err.max() == 0.0


def test_compute_error_map_normalized_to_unit():
    img = np.zeros((8, 8), dtype=np.float32)
    recon = np.zeros((8, 8), dtype=np.float32)
    img[0, 0] = 1.0  # 차이 1.0 -> normalize 후 max=1.0
    err = compute_error_map(img, recon)
    assert abs(err.max() - 1.0) < 1e-6


def test_apply_roi_mask_zeroes_outside():
    err = np.full((4, 4), 0.5, dtype=np.float32)
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[:2, :2] = 1
    masked = apply_roi_mask(err, mask)
    assert masked[0, 0] == 0.5
    assert masked[3, 3] == 0.0
