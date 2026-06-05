# 히트맵 구현 가이드

## 목차
1. [개요](#개요)
2. [구현 과정](#구현-과정)
3. [주요 함수 설명](#주요-함수-설명)
4. [Threshold 기반 접근 방식](#threshold-기반-접근-방식)
5. [사용 예시](#사용-예시)
6. [결과 이미지](#결과-이미지)

---

## 개요

이 문서는 이상 탐지 모델의 히트맵(Heatmap) 시각화 구현 과정과 방법을 설명합니다. 히트맵은 모델이 이상 영역을 어디서 탐지했는지 시각적으로 보여주는 중요한 도구입니다.

### 핵심 목표
- **명확한 시각화**: 이상 영역만 명확하게 표시
- **일관된 임계값**: 모델의 실제 threshold 기반 히트맵 생성
- **대비 극대화**: 정상 영역은 억제하고 이상 영역은 강조

---

## 구현 과정

### 1단계: 초기 구현 (Percentile 기반)

초기에는 percentile 기반 정규화를 사용했습니다:
- `percentile_norm`: 상위 N% 값만 강조
- 문제점: 이미지마다 threshold가 달라 일관성 부족

```python
# 초기 방식 (문제점 발견)
heat = percentile_norm(score_np, low_percentile=0.0, high_percentile=99.5)
heat_enhanced = enhance_heatmap_contrast(heat, threshold_percentile=98.0)
```

### 2단계: Threshold 기반 접근 방식 도입

모델 평가에서 찾은 최적 threshold를 기준으로 히트맵을 생성하도록 개선:

```python
# 개선된 방식
threshold = load_threshold_from_evaluation()  # 예: 3.16e-09
heat_enhanced = enhance_heatmap_with_threshold(score_np, threshold)
```

**장점:**
- 모든 이미지에 동일한 threshold 적용
- 평가 결과와 일치하는 시각화
- 모델의 실제 판단 기준과 일치

### 3단계: 대비 극대화

정상 영역과 이상 영역의 차이를 극대화:
- 이상 영역 (threshold 이상): 0.5 ~ 1.0 범위로 강조
- 정상 영역 (threshold 미만): 0 ~ 0.1 범위로 억제

### 4단계: Threshold 미만 값 시각화 개선 (2024년 최신 업데이트)

**문제점**: Threshold를 넘지 않는 비정상 데이터가 overlay에 표시되지 않음

**해결책**: Threshold 미만 값도 일정 범위까지 시각화하도록 개선:
- Threshold 미만 값: 0 ~ 0.4 범위로 확장하여 시각화
- 로그 스케일 매핑으로 부드러운 분포
- Overlay에서도 threshold 미만 값이 점진적으로 표시됨

---

## 주요 함수 설명

### 1. `enhance_heatmap_with_threshold()`

모델의 실제 threshold를 기준으로 히트맵을 정규화합니다.

**위치**: `mvtec_root/chest_xray/utils.py`, `feature_distance/utils.py`

```python
def enhance_heatmap_with_threshold(heat: np.ndarray, threshold: float, 
                                   gamma: float = 0.3, suppress_factor: float = 0.02,
                                   show_below_threshold: bool = True, below_threshold_max: float = 0.4):
    """모델의 실제 threshold를 기준으로 히트맵 대비 극대화
    
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
```

**작동 원리:**
1. **이상 영역 처리** (heat >= threshold):
   - threshold를 최소값으로, heat의 최대값을 최대값으로 사용
   - 0.5 ~ 1.0 범위로 정규화 (감마 보정 적용)
   
2. **정상 영역 처리** (heat < threshold):
   - **기존 방식** (`show_below_threshold=False`): 0 ~ 0.1 범위로 매우 작게 억제
   - **개선된 방식** (`show_below_threshold=True`, 기본값):
     - threshold 대비 비율로 계산
     - 로그 스케일 매핑으로 0 ~ `below_threshold_max` (기본값: 0.4) 범위로 확장
     - 비정상 데이터라도 threshold를 넘지 않으면 이 범위에 표시됨

**예시:**
```python
# threshold = 3.16e-09
heat_original = np.array([1e-12, 5e-10, 5e-09, 1e-08])  # 원본 값

# 기존 방식 (show_below_threshold=False)
heat_enhanced_old = enhance_heatmap_with_threshold(
    heat_original, threshold, show_below_threshold=False
)
# 결과: [0.0, 0.002, 0.7, 0.95]  # threshold 미만은 거의 0

# 개선된 방식 (show_below_threshold=True, 기본값)
heat_enhanced_new = enhance_heatmap_with_threshold(
    heat_original, threshold, show_below_threshold=True, below_threshold_max=0.4
)
# 결과: [0.0, 0.15, 0.7, 0.95]  # threshold 미만도 0~0.4 범위로 표시
```

### 2. `overlay_heatmap_on_image()`

히트맵을 원본 이미지에 오버레이합니다.

**위치**: `mvtec_root/chest_xray/utils.py`, `feature_distance/utils.py`

```python
def overlay_heatmap_on_image(img: np.ndarray, heat: np.ndarray, alpha: float = 0.7, 
                            threshold: float = 0.5, use_hot_cmap: bool = True,
                            show_below_threshold: bool = True):
    """이미지에 히트맵 오버레이 - 이상 영역 강조 개선
    
    Args:
        img: [H,W] 또는 [H,W,3] 형태의 이미지 (0~1 정규화)
        heat: [H,W] 형태의 히트맵 (0~1 정규화, threshold 기준으로 이미 정규화됨)
        alpha: 오버레이 투명도 (기본값: 0.7)
        threshold: 정규화된 히트맵에서 이상 영역 기준 (기본값: 0.5)
        use_hot_cmap: True면 'hot' 컬러맵, False면 'jet' 컬러맵 사용
        show_below_threshold: threshold 미만 값도 표시할지 여부 (기본값: True)
    """
```

**작동 원리:**
1. **컬러맵 선택**: 'hot' 컬러맵 사용 (검은색 → 빨간색 → 노란색 → 흰색)
2. **가중치 계산**:
   - **기존 방식** (`show_below_threshold=False`):
     - 정상 영역 (heat < 0.5): alpha * 0.03 (거의 보이지 않음)
     - 이상 영역 (heat >= 0.5): alpha (강하게 표시)
   - **개선된 방식** (`show_below_threshold=True`, 기본값):
     - Threshold 미만 영역 (0 < heat < 0.5): alpha * (0.1 ~ 0.3) 점진적 표시
     - Threshold 이상 영역 (heat >= 0.5): alpha (강하게 표시)
     - 매우 높은 영역 (heat >= 0.8): alpha * 1.4 (최대 0.95까지)
3. **블렌딩**: `output = (1 - weight) * image + weight * heatmap_color`

**시각화 범위:**
- **0 ~ 0.4**: Threshold 미만 (낮은 이상 가능성) → 연한 색상으로 점진적 표시
- **0.5 ~ 1.0**: Threshold 이상 (높은 이상 가능성) → 진한 색상으로 강조

### 3. `save_image()`

히트맵을 컬러맵으로 변환하여 저장합니다.

```python
def save_image(array: np.ndarray, path: str, use_colormap: bool = False, cmap_name: str = 'hot'):
    """numpy 배열을 이미지로 저장
    
    Args:
        array: [H,W] 또는 [H,W,3] 형태의 배열 (0~1 정규화)
        path: 저장 경로
        use_colormap: True면 컬러맵 적용 (히트맵용)
        cmap_name: 컬러맵 이름 (기본값: 'hot')
    """
```

---

## Threshold 기반 접근 방식

### Threshold 자동 로드

추론 시 평가 결과에서 threshold를 자동으로 로드합니다:

```python
# evaluation_results/evaluation_results.json에서 자동 로드
eval_json_path = 'evaluation_results/evaluation_results.json'
with open(eval_json_path, 'r') as f:
    eval_data = json.load(f)
    threshold = eval_data['binary_classification']['threshold']
    # 예: threshold = 3.1639799669136437e-09
```

**Fallback 메커니즘:**
1. 평가 결과 JSON 파일에서 로드 (우선)
2. 없으면 첫 10개 샘플로 추정
3. 모두 없으면 percentile 기반 방식 사용 (backward compatibility)

### Threshold 적용 예시

```python
# Dual Anomaly 모델
if threshold is not None:
    # 원본 점수를 threshold 기준으로 정규화 (threshold 미만 값도 시각화)
    score_map_enhanced = enhance_heatmap_with_threshold(
        score_np, threshold, 
        gamma=0.3, 
        suppress_factor=0.02,
        show_below_threshold=True,  # threshold 미만 값도 표시
        below_threshold_max=0.4     # threshold 미만 값의 최대 시각화 범위
    )
else:
    # Fallback: percentile 기반
    score_map = percentile_norm(score_np, low_percentile=0.0, high_percentile=99.5)
    score_map_enhanced = enhance_heatmap_contrast(score_map, threshold_percentile=98.0)
```

---

## 사용 예시

### Dual Anomaly 모델 히트맵 생성

```python
# inference.py에서
xrec, score, s_recon, s_feat, r = model(x)

# 이미지 레벨 스코어 계산
score_np = score[0, 0].cpu().numpy()
flat = score_np.reshape(-1)
k = max(1, int(0.01 * flat.size))
score_img = float(np.mean(np.sort(flat)[-k:]))

# Threshold 기반 히트맵 생성 (threshold 미만 값도 시각화)
if threshold is not None:
    score_map_enhanced = enhance_heatmap_with_threshold(
        score_np, threshold, 
        gamma=0.3, 
        suppress_factor=0.02,
        show_below_threshold=True,  # threshold 미만 값도 표시
        below_threshold_max=0.4     # threshold 미만 값의 최대 시각화 범위
    )

# 오버레이 생성 (threshold 미만 값도 표시)
img_np = minmax_norm(x[0, 0].cpu().numpy())
overlay = overlay_heatmap_on_image(
    img_np, score_map_enhanced, 
    alpha=0.7, 
    threshold=0.5, 
    use_hot_cmap=True,
    show_below_threshold=True  # threshold 미만 값도 표시
)

# 저장
save_image(score_map_enhanced, 'score.png', use_colormap=True, cmap_name='hot')
save_image(overlay, 'overlay.png')
```

### Feature Distance 모델 히트맵 생성

```python
# feature_distance/inference.py에서
dmin = cosine_distance(feats, gallery).min(dim=1).values  # 최소 거리
heat = dmin.reshape(H, W).cpu().numpy()

# Threshold 기반 히트맵 생성
if threshold is not None:
    heat_enhanced = enhance_heatmap_with_threshold(heat, threshold, 
                                                   gamma=0.3, suppress_factor=0.02)

# 오버레이 및 저장
overlay = overlay_heatmap_on_image(img_np, heat_enhanced, 
                                   alpha=0.7, threshold=0.5, use_hot_cmap=True)
save_image(heat_enhanced, 'fd_heat.png', use_colormap=True, cmap_name='hot')
save_image(overlay, 'fd_overlay.png')
```

---

## 결과 이미지

### Dual Anomaly 모델 출력

각 추론 결과는 다음 6개의 이미지를 생성합니다:

1. **`*_input.png`**: 원본 이미지
2. **`*_recon.png`**: 재구성된 이미지 (Autoencoder 출력)
3. **`*_score.png`**: 이상 점수 히트맵 (hot 컬러맵) - **최종 이상 점수**
4. **`*_s_recon.png`**: 복원 오차 히트맵 (hot 컬러맵) - 재구성 오차
5. **`*_s_feat.png`**: 특징 공간 히트맵 (hot 컬러맵) - 특징 attention
6. **`*_overlay.png`**: 원본 이미지 + 히트맵 오버레이 - **최종 시각화**

**파일명 형식:**
```
{idx:05d}_label{label}_score{score:.2e}_{type}.png

예시:
00020_label2_score5.96e-08_input.png      # 원본
00020_label2_score5.96e-08_score.png      # 이상 점수 히트맵
00020_label2_score5.96e-08_overlay.png    # 오버레이
00020_label2_score5.96e-08_recon.png      # 재구성
00020_label2_score5.96e-08_s_recon.png    # 재구성 오차
00020_label2_score5.96e-08_s_feat.png     # 특징 attention
```

### 예시 이미지 설명

실제 생성된 히트맵은 `outs_dual/` 디렉토리에서 확인할 수 있습니다.

#### 정상 케이스 (label=0) 예시

**파일**: `00000_label0_score3.76e-09_*.png`

```
📷 input.png:        원본 흉부 X-ray 이미지
📷 recon.png:        Autoencoder가 재구성한 이미지
📷 score.png:        이상 점수 히트맵 (대부분 검은색, 이상 영역 없음)
📷 s_recon.png:      재구성 오차 히트맵
📷 s_feat.png:       특징 공간 히트맵
📷 overlay.png:      원본 + 히트맵 (이상 영역 거의 없음, 원본이 그대로 보임)
```

**특징:**
- Score 히트맵이 거의 검은색 (이상 없음)
- Overlay에서 원본 이미지가 그대로 보임 (히트맵 영향 최소)

#### 이상 케이스 (label=2, Tuberculosis) 예시

**파일**: `00020_label2_score5.96e-08_*.png`

```
📷 input.png:        원본 흉부 X-ray 이미지 (폐결핵 의심 영역 존재)
📷 recon.png:        Autoencoder가 재구성한 이미지
📷 score.png:        이상 점수 히트맵 (빨간색/노란색 영역으로 이상 표시)
📷 s_recon.png:      재구성 오차 히트맵 (복원 실패 영역)
📷 s_feat.png:       특징 공간 히트맵 (attention이 집중한 영역)
📷 overlay.png:      원본 + 히트맵 (이상 영역이 빨간색/노란색으로 명확하게 표시됨)
```

**특징:**
- Score 히트맵에서 이상 영역이 빨간색/노란색으로 표시
- Overlay에서 원본 이미지 위에 이상 영역이 명확하게 강조됨
- Score 값이 threshold (3.16e-09)보다 높음 (5.96e-08)

#### 각 히트맵의 역할

| 히트맵 | 설명 | 용도 |
|--------|------|------|
| `score.png` | 최종 이상 점수 (s_recon + s_feat 결합) | **주요 참고용** - 최종 이상 탐지 결과 |
| `s_recon.png` | 재구성 오차 (원본 - 재구성) | 복원 실패 영역 확인 |
| `s_feat.png` | 특징 공간 attention | 모델이 주목한 특징 영역 확인 |
| `overlay.png` | 원본 + score 히트맵 | **시각화용** - 이상 영역을 원본과 함께 확인 |

### 히트맵 색상 의미

'hot' 컬러맵을 사용하며, 다음 의미를 가집니다:

```
검은색 → 빨간색 → 노란색 → 흰색
  ↓        ↓        ↓        ↓
정상    약한     중간     매우 높은
      이상 신호  이상 신호  이상 신호
```

- **검은색/어두운 색**: 정상 영역 (heat ≈ 0)
- **어두운 빨간색**: 낮은 이상 가능성 (threshold 미만, 0 < heat < 0.4) - **새로 추가됨**
- **빨간색**: 이상 가능성 중간 (threshold 이상, 0.5 ≤ heat < 0.8)
- **노란색**: 이상 가능성 높음 (0.8 ≤ heat < 0.95)
- **흰색**: 이상 가능성 매우 높음 (heat ≥ 0.95)

**참고**: Threshold 미만 값도 이제 시각화되므로, 비정상 데이터라도 threshold를 넘지 않으면 어두운 빨간색으로 표시됩니다.

### 실제 확인 방법

```bash
# outs_dual 디렉토리에서 예시 확인
cd outs_dual

# 정상 케이스 (label=0)
ls 00000_label0_score*.*
# 00000_label0_score3.76e-09_input.png
# 00000_label0_score3.76e-09_score.png
# 00000_label0_score3.76e-09_overlay.png
# ...

# 이상 케이스 (label=2, Tuberculosis)
ls 00020_label2_score*.*
# 00020_label2_score5.96e-08_input.png
# 00020_label2_score5.96e-08_score.png
# 00020_label2_score5.96e-08_overlay.png
# ...
```

**주의사항:**
- `score.png`와 `overlay.png`가 가장 중요합니다
- `overlay.png`는 원본 이미지와 히트맵을 결합하여 이상 영역을 직관적으로 보여줍니다
- Score 값이 threshold보다 높을수록 이상 가능성이 높습니다

---

## 개선 사항 요약

### 문제점과 해결

1. **문제**: Percentile 기반 방식으로 이미지마다 threshold가 달라 일관성 부족
   - **해결**: 모델 평가 결과의 실제 threshold 사용

2. **문제**: 히트맵이 전체적으로 노란색으로 표시되어 이상 영역 구분 어려움
   - **해결**: Threshold 기준으로 정상 영역 강하게 억제 (0.02 배율)

3. **문제**: Score가 0으로 표시되는 문제 (매우 작은 값)
   - **해결**: 파일명에 과학적 표기법 사용 (`:.2e`)

4. **문제**: 히트맵이 직관적이지 못함
   - **해결**: 
     - 'hot' 컬러맵 사용 (이상 영역 강조에 적합)
     - 가중치 기반 오버레이 (이상 영역만 강하게 표시)
     - 감마 보정으로 대비 향상

5. **문제**: Threshold를 넘지 않는 비정상 데이터가 overlay에 표시되지 않음
   - **해결**: 
     - `show_below_threshold=True` 파라미터 추가 (기본값)
     - Threshold 미만 값을 0 ~ 0.4 범위로 확장하여 시각화
     - 로그 스케일 매핑으로 부드러운 분포
     - Overlay에서 threshold 미만 값도 점진적으로 표시 (alpha 0.1 ~ 0.3)
     - 비정상 데이터라도 threshold를 넘지 않으면 어두운 빨간색으로 표시됨

---

## 기술 스택

- **NumPy**: 배열 연산 및 정규화
- **Matplotlib**: 컬러맵 생성 ('hot' colormap)
- **PIL (Pillow)**: 이미지 저장
- **PyTorch**: 모델 추론 및 텐서 연산

---

## 참고 파일

- **핵심 함수**: `mvtec_root/chest_xray/utils.py`
- **추론 코드**: `mvtec_root/chest_xray/inference.py`
- **Feature Distance**: `feature_distance/inference.py`, `feature_distance/utils.py`
- **평가 결과**: `evaluation_results/evaluation_results.json`

---

## 최종 결과

Threshold 기반 히트맵을 통해:
- ✅ 모든 이미지에 동일한 임계값 적용 (일관성)
- ✅ 모델 평가 결과와 일치하는 시각화 (정확성)
- ✅ 이상 영역만 명확하게 표시 (직관성)
- ✅ 정상 영역은 거의 보이지 않도록 억제 (명확성)
- ✅ Threshold 미만 값도 시각화하여 비정상 데이터 누락 방지 (완전성)

이러한 개선으로 히트맵이 모델의 실제 판단 기준을 정확하게 반영하며, 의료진이 이상 영역을 쉽게 식별할 수 있게 되었습니다. 특히 threshold를 넘지 않는 비정상 데이터도 overlay에 표시되어 놓치는 경우를 줄일 수 있습니다.

