#!/usr/bin/env python3
"""
유틸리티 함수 모듈
"""

import random
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import matplotlib.pyplot as plt


def seed_everything(seed: int = 42):
    """모든 랜덤 시드 고정"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def ensure_dir(path: str):
    """디렉토리 생성 (부모 디렉토리 포함)"""
    Path(path).mkdir(parents=True, exist_ok=True)


def save_image(array: np.ndarray, path: str, use_colormap: bool = False, cmap_name: str = 'hot'):
    """numpy 배열을 이미지로 저장
    
    Args:
        array: [H,W] 또는 [H,W,3] 형태의 배열 (0~1 정규화)
        path: 저장 경로
        use_colormap: True면 컬러맵 적용 (히트맵용)
        cmap_name: 컬러맵 이름 (기본값: 'hot')
    """
    arr = np.clip(array, 0, 1)
    
    if use_colormap and arr.ndim == 2:
        # 히트맵을 컬러맵으로 변환
        cmap = plt.get_cmap(cmap_name)
        arr_colored = cmap(arr)[..., :3]  # RGB만 추출
        arr_colored = (arr_colored * 255).astype(np.uint8)
        img = Image.fromarray(arr_colored)
    else:
        if arr.ndim == 2:
            # Grayscale
            img = Image.fromarray((arr * 255).astype(np.uint8), mode='L')
        else:
            # RGB
            img = Image.fromarray((arr * 255).astype(np.uint8))
    
    img.save(path)


def overlay_heatmap_on_image(img: np.ndarray, heat: np.ndarray, alpha: float = 0.7, 
                            threshold: float = 0.3, use_hot_cmap: bool = True,
                            show_below_threshold: bool = True):
    """이미지에 히트맵 오버레이 - 이상 영역 강조 개선 (대비 극대화)
    
    Args:
        img: [H,W] 또는 [H,W,3] 형태의 이미지 (0~1 정규화)
        heat: [H,W] 형태의 히트맵 (0~1 정규화)
        alpha: 오버레이 투명도 (기본값: 0.7, 높을수록 히트맵이 더 진하게)
        threshold: 이 값 이상인 히트맵 영역만 강조 (기본값: 0.3, 낮을수록 더 많은 영역 강조)
        use_hot_cmap: True면 'hot' 컬러맵, False면 'jet' 컬러맵 사용
        show_below_threshold: threshold 미만 값도 표시할지 여부 (기본값: True)
    Returns:
        오버레이된 이미지 배열
    """
    if img.ndim == 2:
        img3 = np.stack([img, img, img], axis=-1)
    else:
        img3 = img
    
    # 컬러맵 선택 (hot이 이상 영역 강조에 더 적합)
    cmap_name = 'hot' if use_hot_cmap else 'jet'
    cmap = plt.get_cmap(cmap_name)
    
    # 대비 극대화: heat가 이미 threshold 기준으로 정규화되었으므로 그대로 사용
    heat_enhanced = heat.copy()
    
    heat_color = cmap(heat_enhanced)[..., :3]
    
    # 가중치 기반 오버레이
    # heat_enhanced는 threshold 기준으로 정규화됨:
    # - 0~0.4: threshold 미만 (낮은 이상 가능성)
    # - 0.5~1.0: threshold 이상 (높은 이상 가능성)
    threshold_normalized = 0.5  # 정규화된 히트맵에서 threshold = 0.5
    
    # 영역별 가중치 설정
    if show_below_threshold:
        # threshold 미만 값도 표시 (0~0.4 범위)
        # 0~0.4 범위: 점진적으로 표시 (0.1~0.3 alpha)
        # 0.5 이상: 강하게 표시 (alpha)
        weight = np.ones_like(heat_enhanced) * alpha * 0.05  # 기본값 (거의 안 보임)
        
        # threshold 미만 영역 (0~0.4): 점진적으로 표시
        mask_below = (heat_enhanced > 0) & (heat_enhanced < threshold_normalized)
        if mask_below.any():
            # 0~0.4 범위를 0.1~0.3 alpha로 매핑
            normalized_below = heat_enhanced[mask_below] / threshold_normalized  # 0~1로 정규화
            weight[mask_below] = alpha * (0.1 + 0.2 * normalized_below)  # 0.1~0.3 alpha
        
        # threshold 이상 영역 (0.5~1.0): 강하게 표시
        mask_above = heat_enhanced >= threshold_normalized
        weight[mask_above] = alpha  # 이상 영역은 강하게
        
        # 매우 높은 영역 (0.8 이상): 더 강하게
        very_high_mask = heat_enhanced >= 0.8
        weight[very_high_mask] = min(alpha * 1.4, 0.95)  # 최대 0.95까지
    else:
        # 기존 방식: threshold 미만은 거의 안 보이게
        mask = heat_enhanced >= threshold_normalized
        weight = np.ones_like(heat_enhanced) * alpha * 0.03  # 정상 영역은 거의 보이지 않게 (3%)
        weight[mask] = alpha  # 이상 영역은 강하게
        # 매우 높은 영역 (0.8 이상)은 더 강하게
        very_high_mask = heat_enhanced >= 0.8
        weight[very_high_mask] = min(alpha * 1.4, 0.95)  # 최대 0.95까지
    
    weight = np.clip(weight, 0, 1)
    
    out = (1 - weight[..., None]) * img3 + weight[..., None] * heat_color
    return np.clip(out, 0, 1)


def minmax_norm(x: np.ndarray, eps: float = 1e-8):
    """Min-Max 정규화"""
    m, M = x.min(), x.max()
    return (x - m) / (M - m + eps)


def percentile_norm(x: np.ndarray, low_percentile: float = 0.0, high_percentile: float = 100.0, eps: float = 1e-8):
    """Percentile 기반 정규화 - 이상 영역 강조에 유용
    
    Args:
        x: 정규화할 배열
        low_percentile: 하한 percentile (기본값: 0.0)
        high_percentile: 상한 percentile (기본값: 100.0)
        eps: 안정성을 위한 작은 값
    Returns:
        정규화된 배열 (0~1 범위)
    """
    p_low = np.percentile(x, low_percentile)
    p_high = np.percentile(x, high_percentile)
    x_clipped = np.clip(x, p_low, p_high)
    if p_high - p_low < eps:
        return np.zeros_like(x)
    return (x_clipped - p_low) / (p_high - p_low + eps)


def enhance_heatmap_with_threshold(heat: np.ndarray, threshold: float, 
                                   gamma: float = 0.3, suppress_factor: float = 0.02,
                                   show_below_threshold: bool = True, below_threshold_max: float = 0.4):
    """모델의 실제 threshold를 기준으로 히트맵 대비 극대화
    
    threshold 이상은 이상 영역으로 강조하고, 미만도 일정 범위까지 시각화합니다.
    
    Args:
        heat: 히트맵 배열 (원본 값, 정규화되지 않음)
        threshold: 모델의 실제 threshold 값 (예: 3.16e-09)
        gamma: 감마 보정 (작을수록 더 강조, 기본값: 0.3)
        suppress_factor: 정상 영역 억제 계수 (기본값: 0.02, 매우 작게)
        show_below_threshold: threshold 미만 값도 시각화할지 여부 (기본값: True)
        below_threshold_max: threshold 미만 값의 최대 시각화 범위 (기본값: 0.4)
    Returns:
        대비가 강화된 히트맵 배열 (0~1 정규화)
    """
    # threshold를 기준으로 정규화
    # threshold 미만: 0~below_threshold_max 범위로 확장 (시각화 가능)
    # threshold 이상: 0.5~1.0 범위로 확장
    heat_enhanced = np.zeros_like(heat, dtype=np.float32)
    
    # threshold 이상 영역 (이상)
    mask_anomaly = heat >= threshold
    if mask_anomaly.any():
        heat_anomaly = heat[mask_anomaly]
        # threshold 이상 값을 0.5~1.0 범위로 매핑
        # 최소값을 threshold로, 최대값은 heat의 최대값으로
        min_anomaly = threshold
        max_anomaly = heat_anomaly.max()
        if max_anomaly > min_anomaly + 1e-12:
            # 로그 스케일 또는 감마 보정으로 강조
            normalized = (heat_anomaly - min_anomaly) / (max_anomaly - min_anomaly + 1e-12)
            # 감마 보정으로 강조
            heat_enhanced[mask_anomaly] = 0.5 + 0.5 * np.power(normalized, gamma)
        else:
            heat_enhanced[mask_anomaly] = 0.7
    
    # threshold 미만 영역 (정상 또는 낮은 이상)
    mask_normal = heat < threshold
    if mask_normal.any() and show_below_threshold:
        heat_normal = heat[mask_normal]
        # threshold 미만 값도 시각화 가능하도록 확장
        if heat_normal.max() > 1e-12:
            # threshold 대비 비율로 계산
            ratio = heat_normal / (threshold + 1e-12)
            # 0~below_threshold_max 범위로 매핑 (로그 스케일 사용)
            # ratio가 0에 가까우면 0, 1에 가까우면 below_threshold_max
            # 로그 스케일로 더 부드럽게 분포
            ratio_clipped = np.clip(ratio, 0, 1)
            # 로그 스케일 적용 (더 부드러운 분포)
            log_ratio = np.log1p(ratio_clipped * 9) / np.log(10)  # 0~1을 0~1로 매핑
            heat_enhanced[mask_normal] = log_ratio * below_threshold_max
        else:
            heat_enhanced[mask_normal] = 0.0
    elif mask_normal.any():
        # show_below_threshold=False인 경우 기존 방식 유지
        heat_normal = heat[mask_normal]
        if heat_normal.max() > 1e-12:
            ratio = heat_normal / (threshold + 1e-12)
            heat_enhanced[mask_normal] = ratio * 0.1 * suppress_factor
        else:
            heat_enhanced[mask_normal] = 0.0
    
    return np.clip(heat_enhanced, 0, 1)


def enhance_heatmap_contrast(heat: np.ndarray, threshold_percentile: float = 98.0, 
                             gamma: float = 0.2, suppress_low: float = 0.01, 
                             enhance_high: bool = True):
    """히트맵 대비 극대화 - 정상과 이상의 차이를 명확하게 (강화된 버전)
    
    상위 2%만 이상 영역으로 강조하고, 나머지는 매우 강하게 억제합니다.
    (percentile 기반 버전, backward compatibility용)
    
    Args:
        heat: 히트맵 배열 (0~1 정규화)
        threshold_percentile: 이상 영역으로 간주할 percentile (기본값: 98.0, 상위 2%)
        gamma: 감마 보정 (작을수록 더 강조, 기본값: 0.2)
        suppress_low: 임계값 미만 영역 억제 비율 (기본값: 0.01, 매우 작게 설정)
        enhance_high: True면 이상 영역 강조, False면 단순히 억제만
    Returns:
        대비가 강화된 히트맵 배열
    """
    heat_enhanced = heat.copy()
    
    # 동적 임계값: 상위 2%만 이상으로 간주 (98th percentile 사용)
    percentile_threshold = np.percentile(heat, threshold_percentile)
    
    # threshold 이상 영역: 강조 (상위 2%만)
    mask_high = heat >= percentile_threshold
    if mask_high.any() and enhance_high:
        # 이상 영역을 더 밝게 (0.8 ~ 1.0 범위로 확장)
        heat_high = heat[mask_high]
        heat_range = heat_high.max() - percentile_threshold + 1e-8
        if heat_range > 1e-8:
            # 감마 보정으로 강조
            heat_enhanced[mask_high] = 0.8 + 0.2 * np.power(
                (heat_high - percentile_threshold) / heat_range, gamma
            )
        else:
            heat_enhanced[mask_high] = 0.9
    elif mask_high.any():
        # enhance_high=False인 경우: threshold 이상도 억제 (s_recon용)
        heat_high = heat[mask_high]
        heat_range = heat_high.max() - percentile_threshold + 1e-8
        if heat_range > 1e-8:
            # 억제 버전: 상위 영역도 중간 정도로만
            heat_enhanced[mask_high] = 0.5 + 0.3 * np.power(
                (heat_high - percentile_threshold) / heat_range, 0.5
            )
        else:
            heat_enhanced[mask_high] = 0.6
    
    # threshold 미만 영역: 매우 강하게 억제 (98% 이상의 픽셀)
    mask_low = heat < percentile_threshold
    if mask_low.any():
        # 정상 영역을 거의 완전히 0에 가깝게 (0 ~ 0.1 범위로 제한)
        heat_low = heat[mask_low]
        low_max = heat_low.max() if mask_low.any() else 1.0
        if low_max > 1e-8:
            # 정상 영역을 매우 작게 (0~0.1 범위로 매우 강하게 제한)
            # median 기반 추가 억제
            median_low = np.median(heat_low)
            heat_enhanced[mask_low] = (heat_low / low_max) * 0.1 * suppress_low * (percentile_threshold / (median_low + 1e-8))
        else:
            heat_enhanced[mask_low] = 0.0
    
    return np.clip(heat_enhanced, 0, 1)


def compute_robust_score(score_map: np.ndarray, method: str = 'trimmed_mean', 
                         top_percentile: float = 1.0, trim_percentile: float = 0.5,
                         use_iqr_filter: bool = True, iqr_factor: float = 1.5):
    """Outlier에 robust한 스코어 계산 함수
    
    Args:
        score_map: [H, W] 형태의 스코어 맵
        method: 집계 방법 ('trimmed_mean', 'median', 'winsorized_mean', 'iqr_median')
        top_percentile: 상위 몇 %를 사용할지 (기본값: 1.0%)
        trim_percentile: 양쪽에서 몇 %를 제거할지 (기본값: 0.5%, 양쪽 합쳐서 1%)
        use_iqr_filter: IQR 기반 outlier 필터링 사용 여부
        iqr_factor: IQR multiplier (기본값: 1.5)
    
    Returns:
        robust score (float)
    """
    flat = score_map.reshape(-1)
    
    # IQR 기반 outlier 필터링 (선택적)
    if use_iqr_filter and len(flat) > 4:
        q1 = np.percentile(flat, 25)
        q3 = np.percentile(flat, 75)
        iqr = q3 - q1
        if iqr > 1e-10:  # IQR이 너무 작으면 필터링 안 함
            lower_bound = q1 - iqr_factor * iqr
            upper_bound = q3 + iqr_factor * iqr
            # Outlier 제거 (하지만 상위 값은 보존)
            mask = (flat >= lower_bound) | (flat >= np.percentile(flat, 99))
            flat = flat[mask]
    
    if len(flat) == 0:
        return float(np.mean(score_map))
    
    # 상위 percentile만 선택
    k = max(1, int(len(flat) * top_percentile / 100.0))
    top_values = np.sort(flat)[-k:]
    
    if method == 'trimmed_mean':
        # 양쪽에서 일정 비율 제거 후 평균
        trim_n = max(0, int(len(top_values) * trim_percentile / 100.0))
        if trim_n > 0 and len(top_values) > 2 * trim_n:
            trimmed = top_values[trim_n:-trim_n] if trim_n > 0 else top_values
        else:
            trimmed = top_values
        return float(np.mean(trimmed))
    
    elif method == 'median':
        # 중앙값 사용 (outlier에 가장 robust)
        return float(np.median(top_values))
    
    elif method == 'winsorized_mean':
        # Winsorized mean: 극단값을 제한한 후 평균
        if len(top_values) > 2:
            p5 = np.percentile(top_values, 5)
            p95 = np.percentile(top_values, 95)
            winsorized = np.clip(top_values, p5, p95)
            return float(np.mean(winsorized))
        else:
            return float(np.mean(top_values))
    
    elif method == 'iqr_median':
        # IQR 기반 중앙값 (더 robust)
        if len(top_values) > 4:
            q1 = np.percentile(top_values, 25)
            q3 = np.percentile(top_values, 75)
            iqr = q3 - q1
            if iqr > 1e-10:
                # IQR 범위 내의 값만 사용
                mask = (top_values >= q1 - iqr_factor * iqr) & (top_values <= q3 + iqr_factor * iqr)
                if mask.sum() > 0:
                    return float(np.median(top_values[mask]))
        return float(np.median(top_values))
    
    else:
        # 기본값: trimmed mean
        return float(np.mean(top_values))


def detect_outliers_iqr(values: np.ndarray, factor: float = 1.5):
    """IQR 기반 outlier 탐지
    
    Args:
        values: 값 배열
        factor: IQR multiplier (기본값: 1.5)
    
    Returns:
        outlier mask (boolean array)
    """
    if len(values) < 4:
        return np.zeros(len(values), dtype=bool)
    
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    
    if iqr < 1e-10:
        return np.zeros(len(values), dtype=bool)
    
    lower_bound = q1 - factor * iqr
    upper_bound = q3 + factor * iqr
    
    return (values < lower_bound) | (values > upper_bound)


def compute_zscore_outliers(values: np.ndarray, threshold: float = 3.0):
    """Z-score 기반 outlier 탐지
    
    Args:
        values: 값 배열
        threshold: Z-score 임계값 (기본값: 3.0)
    
    Returns:
        outlier mask (boolean array)
    """
    if len(values) < 3:
        return np.zeros(len(values), dtype=bool)
    
    mean = np.mean(values)
    std = np.std(values)
    
    if std < 1e-10:
        return np.zeros(len(values), dtype=bool)
    
    z_scores = np.abs((values - mean) / std)
    return z_scores > threshold