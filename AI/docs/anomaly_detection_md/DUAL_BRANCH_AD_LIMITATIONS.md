# Anomaly Detection의 한계와 개선 방안

## 현재 성능 분석

### 평가 결과 요약

**이진 분류 (정상 vs 이상):**
- PR-AUC: 0.93 ✅ (매우 좋음)
- F1-Score: 0.83 ✅ (양호)
- ROC-AUC: 0.51 ⚠️ (랜덤 수준)

**다중 클래스 분류 (질병별 구분):**
- 모든 클래스 ROC-AUC: 0.4~0.6 ❌ (랜덤 수준)
- 질병별 구분이 거의 불가능

## 왜 이런 현상이 발생하는가?

### 1. Anomaly Detection의 본질적 한계

Anomaly Detection은 **정상 데이터만으로 학습**합니다:
- ✅ 정상 패턴을 학습 → "이것이 정상이 아니다" 판단 가능
- ❌ 이상 데이터의 종류를 구분하는 정보가 없음
- ❌ 모든 이상이 비슷한 "비정상성" 점수를 받음

### 2. 현재 모델의 동작 방식

```
정상 이미지 → 낮은 anomaly score
이상 이미지 (pneumonia) → 높은 anomaly score
이상 이미지 (tuberculosis) → 높은 anomaly score
이상 이미지 (기타 질병) → 높은 anomaly score
```

**문제:** 모든 이상이 비슷한 높은 점수를 받아서 **어떤 질병인지 구분 불가**

### 3. ROC-AUC가 낮은 이유

- **불균형 데이터**: 정상 100개 vs 이상 1400개
- **Threshold 문제**: 최적 threshold가 거의 0에 가까움 (3.16e-09)
- **이상 데이터가 너무 많아서** 정상/이상 구분도 어려움

## 개선 방안

### 방안 1: Multi-Class Classifier 추가 (권장)

Anomaly Detection + Classification 하이브리드 접근:

```python
# 1단계: Anomaly Detection (정상 vs 이상)
if anomaly_score > threshold:
    # 2단계: Classification (어떤 질병인지)
    disease_class = classifier.predict(image)
```

**장점:**
- Anomaly detection으로 이상 탐지
- Classifier로 질병 구분
- 두 단계로 나누어 각각 최적화 가능

**구현 방법:**
1. 기존 anomaly detector로 이상 탐지
2. 이상으로 판단된 이미지만 classifier에 입력
3. Classifier는 모든 질병 클래스로 학습 (supervised learning)

### 방안 2: 질병별 Anomaly Detector 학습

각 질병마다 별도의 anomaly detector 학습:

```python
# 정상 데이터로 학습
normal_detector = train_anomaly_detector(normal_images)

# 각 질병별로 "정상"으로 간주하고 학습
pneumonia_detector = train_anomaly_detector(normal_images + pneumonia_images)
tuberculosis_detector = train_anomaly_detector(normal_images + tuberculosis_images)
```

**장점:**
- 각 질병의 특징을 학습
- 질병별로 다른 anomaly score 분포

**단점:**
- 모델 수가 많아짐 (질병 수만큼)
- 학습 시간 증가

### 방안 3: Feature-Based Classification

Anomaly detector의 latent feature를 활용한 classification:

```python
# 1. Anomaly detector에서 feature 추출
features = anomaly_detector.extract_features(image)

# 2. Feature로 질병 분류
disease_class = classifier(features)
```

**장점:**
- Anomaly detector의 학습된 특징 활용
- 추가 학습 데이터 필요 적음

### 방안 4: Threshold 조정 및 후처리

현재 threshold가 너무 낮음 (거의 0):
- Threshold를 높여서 더 확실한 이상만 탐지
- 이상 탐지 후 추가 분류 단계 추가

## 권장 접근 방법

### 단계별 구현

1. **1단계: Anomaly Detection (현재 모델 유지)**
   - 정상 vs 이상 구분 ✅ (현재 잘 작동)
   - PR-AUC 0.93, F1 0.83 유지

2. **2단계: Multi-Class Classifier 추가**
   - 이상 데이터로 학습된 classifier
   - 이상으로 판단된 이미지만 분류
   - 질병별 구분 성능 향상

3. **3단계: 하이브리드 시스템**
   ```
   이미지 입력
   ↓
   Anomaly Detection (정상/이상 판단)
   ↓
   [이상인 경우]
   ↓
   Multi-Class Classifier (질병 구분)
   ↓
   최종 결과: 정상 or 질병명
   ```

## 코드 구현 예시

### Multi-Class Classifier 추가

```python
# classifier.py
import torch
import torch.nn as nn
from model import SimpleAE

class DiseaseClassifier(nn.Module):
    """질병 분류기 (이상 데이터로 학습)"""
    def __init__(self, num_classes=15):
        super().__init__()
        # Anomaly detector의 encoder 활용
        self.encoder = SimpleAE(in_ch=1, latent_ch=128).enc
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x):
        features = self.encoder(x)
        logits = self.classifier(features)
        return logits
```

### 하이브리드 추론

```python
def hybrid_inference(image, anomaly_detector, classifier, anomaly_threshold=0.01):
    # 1. Anomaly Detection
    anomaly_score = anomaly_detector.predict(image)
    
    if anomaly_score < anomaly_threshold:
        return "정상", anomaly_score
    else:
        # 2. Classification
        disease_logits = classifier(image)
        disease_class = torch.argmax(disease_logits, dim=1)
        return disease_class, anomaly_score
```

## 결론

**Anomaly Detection만으로는 질병 구분이 어렵습니다.** 이는 본질적 한계입니다.

**해결책:**
- ✅ Anomaly Detection: 정상 vs 이상 구분 (현재 잘 작동)
- ➕ Multi-Class Classifier: 이상 중에서 질병 구분 (추가 필요)

두 가지를 결합하면 **이상 탐지 + 질병 분류** 모두 가능합니다.

