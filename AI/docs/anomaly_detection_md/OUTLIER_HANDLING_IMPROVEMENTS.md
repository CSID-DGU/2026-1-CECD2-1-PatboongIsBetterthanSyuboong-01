# Dual Branch Anomaly Detection - Outlier 처리 개선

## 개요

기존 dual_branch 구조의 anomaly detection 모델에서 outlier 처리 부재로 인한 오분류 문제를 해결하기 위해 robust statistics 기반의 outlier 처리 메커니즘을 추가했습니다.

## 발견된 문제점

### 1. 스코어 계산 방식의 문제
- **기존 방식**: 상위 1% 평균값만 사용
- **문제점**: 
  - 극단적인 outlier 하나가 전체 스코어를 왜곡시킬 수 있음
  - 정상 이미지가 비정상으로, 비정상 이미지가 정상으로 잘못 분류되는 경우 발생

### 2. Outlier 처리 부재
- IQR, z-score, robust statistics 같은 outlier 처리 메커니즘이 전혀 없음
- 단순 평균 기반 계산으로 outlier에 취약

### 3. 학습 과정의 문제
- 단순 L1 loss와 평균 스코어만 사용
- Outlier에 robust한 loss function 부재

### 4. ADRM 모듈의 문제
- 두 브랜치를 단순 곱셈으로 결합
- Outlier가 있는 경우 잘못된 스코어 생성

## 구현된 개선 사항

### 1. Robust Statistics 기반 스코어 계산 (`utils.py`)

#### `compute_robust_score()` 함수
- **위치**: `mvtec_root/chest_xray/utils.py`
- **기능**: Outlier에 robust한 스코어 계산
- **지원하는 방법**:
  - `trimmed_mean`: 양쪽에서 일정 비율 제거 후 평균
  - `median`: 중앙값 사용 (가장 robust)
  - `winsorized_mean`: 극단값을 제한한 후 평균
  - `iqr_median`: IQR 기반 중앙값
- **특징**:
  - IQR 기반 outlier 필터링 옵션
  - 상위 percentile만 선택하여 계산
  - Outlier의 영향을 최소화

#### `detect_outliers_iqr()` 함수
- IQR 기반 outlier 탐지
- 1.5 * IQR 규칙 사용

#### `compute_zscore_outliers()` 함수
- Z-score 기반 outlier 탐지
- 기본 임계값: 3.0

### 2. ADRM 모듈 개선 (`model.py`)

#### Outlier Suppression 메커니즘 추가
- **위치**: `mvtec_root/chest_xray/model.py`의 `ADRM2D` 클래스
- **기능**:
  - 각 단계에서 percentile 기반 outlier suppression
  - 상위 99.5 percentile을 초과하는 값 제한
  - 두 브랜치 결합 전후 모두에 적용

```python
class ADRM2D(nn.Module):
    def __init__(self, outlier_suppression: bool = True, suppression_percentile: float = 99.5):
        # ...
    
    def _suppress_outliers(self, x):
        # Percentile 기반 outlier clipping
        # ...
```

### 3. Robust Loss Functions (`train.py`)

#### `HuberLoss` 클래스
- **위치**: `mvtec_root/chest_xray/train.py`
- **기능**: Reconstruction loss에 사용
- **특징**: Outlier에 robust한 loss function
  - 작은 오차: L2 loss (quadratic)
  - 큰 오차: L1 loss (linear)
  - Delta 파라미터로 전환점 조절

#### `RobustScoreLoss` 클래스
- **기능**: Score loss에 사용
- **특징**: 
  - 상위 percentile만 사용하여 outlier의 영향을 줄임
  - 기본값: 95th percentile

### 4. Inference 개선 (`inference.py`)

#### Robust Score 계산 적용
- **기본값**: `trimmed_mean` with IQR filtering
- **옵션**: `use_robust_score` 플래그로 활성화/비활성화 가능
- **Backward compatibility**: 기존 방식도 지원

```python
# Robust score 계산
score_img = compute_robust_score(
    score_np, 
    method='trimmed_mean',
    top_percentile=1.0,
    trim_percentile=0.5,
    use_iqr_filter=True,
    iqr_factor=1.5
)
```

## 사용 방법

### 학습 시

```python
# Robust loss 사용 (기본값: True)
args.use_robust_loss = True
train_dual_anomaly(args)
```

### 추론 시

```python
# Robust score 계산 사용 (기본값: True)
args.use_robust_score = True
infer_dual_anomaly(args)
```

### Robust Score 방법 선택

```python
# Inference에서 다른 방법 사용
score_img = compute_robust_score(
    score_np,
    method='median',  # 또는 'winsorized_mean', 'iqr_median'
    top_percentile=1.0,
    use_iqr_filter=True
)
```

## 예상 개선 효과

### 1. 정확도 향상
- Outlier로 인한 오분류 감소
- 정상/비정상 구분 정확도 향상

### 2. 안정성 향상
- 극단적인 값에 덜 민감
- 더 일관된 스코어 분포

### 3. Robustness 향상
- 다양한 데이터 분포에 대응 가능
- 노이즈에 강건함

## 성능 비교

### 기존 방식
- 스코어 계산: 상위 1% 평균
- Outlier 처리: 없음
- Loss: L1 + 평균 스코어

### 개선된 방식
- 스코어 계산: Trimmed mean with IQR filtering
- Outlier 처리: Percentile clipping + IQR filtering
- Loss: Huber + Robust score loss

## 추가 개선 가능 사항

1. **Adaptive Threshold**: 데이터 분포에 따라 자동으로 threshold 조정
2. **Ensemble Methods**: 여러 robust statistics 방법의 결과를 결합
3. **Online Outlier Detection**: 학습 중 실시간 outlier 탐지 및 처리
4. **Hyperparameter Tuning**: Robust score 계산의 하이퍼파라미터 최적화

## 참고 사항

- 모든 개선 사항은 **backward compatible**하게 구현되어 기존 코드와 호환됩니다.
- `use_robust_loss`와 `use_robust_score` 플래그로 기존 방식으로 되돌릴 수 있습니다.
- 기본값은 모두 **True**로 설정되어 자동으로 robust 방법이 사용됩니다.

## 파일 변경 사항

1. `mvtec_root/chest_xray/utils.py`: Robust statistics 함수 추가
2. `mvtec_root/chest_xray/model.py`: ADRM에 outlier suppression 추가
3. `mvtec_root/chest_xray/train.py`: Robust loss functions 추가
4. `mvtec_root/chest_xray/inference.py`: Robust score 계산 적용

