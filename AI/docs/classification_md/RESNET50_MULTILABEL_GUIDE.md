# ResNet101 Multi-Label Classification Guide (개선 버전)

`mvtec_root/chest_xray/resnet50_multilabel.py` 스크립트는 **ResNet101 with CBAM Attention**을 사용하여 CheXpert 형식의 CSV 데이터를 기반으로 흉부 X-ray 이미지에 대한 멀티레이블 분류를 수행합니다.

## 🆕 주요 개선 사항

- ✅ **ResNet101**: 더 깊은 네트워크로 성능 향상
- ✅ **CBAM Attention**: Channel & Spatial Attention으로 중요한 특징 강조
- ✅ **Undersampling**: 클래스 불균형 문제 해소
- ✅ **Early Stopping**: 과적합 방지 및 학습 시간 단축
- ✅ **클래스별 최적 임계값**: 각 클래스마다 F1-score 최대화하는 임계값 자동 탐색
- ✅ **향상된 데이터 증강**: ColorJitter 추가
- ✅ **ImageNet 사전학습**: 의료 영상에 전이 학습 적용

---

## 1. 준비 사항

- Python 3.10 이상
- `requirements.txt` 설치 (torch / torchvision / scikit-learn 등)
- `mvtec_root/chest_xray/archive/` 폴더에 다음 파일들이 있어야 함:
  - `train.csv`: 학습용 CSV 파일
  - `valid.csv`: 검증용 CSV 파일
  - `train/`, `valid/`: 이미지 파일들이 저장된 디렉토리
- CUDA GPU 권장 (ResNet101은 메모리 사용량이 큼)

```powershell
cd C:\Project\AI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. 데이터 구조

### CSV 형식

CSV 파일은 CheXpert 형식을 따릅니다:
- 첫 번째 컬럼: `Path` (이미지 파일 경로)
- 나머지 컬럼: 각 질병 라벨 (14개)
  - `1`: 양성 (Positive)
  - `0`: 음성 (Negative)
  - `-1`: 불확실 (Uncertain) - `--uncertain_policy`로 처리 방식 결정

### 디렉토리 구조 예시

```
mvtec_root/chest_xray/
├─ archive/
│  ├─ train.csv
│  ├─ valid.csv
│  ├─ train/
│  │  └─ patient00001/
│  │     └─ study1/
│  │        └─ view1_frontal.jpg
│  └─ valid/
│     └─ patient64541/
│        └─ study1/
│           └─ view1_frontal.jpg
└─ resnet50_multilabel.py
```

### 지원하는 라벨 (14개)

1. Atelectasis
2. Cardiomegaly
3. Consolidation
4. Edema
5. Enlarged Cardiomediastinum
6. Fracture
7. Lung Lesion
8. Lung Opacity
9. No Finding
10. Pleural Effusion
11. Pleural Other
12. Pneumonia
13. Pneumothorax
14. Support Devices

---

## 3. 실행 방법

### 기본 실행 (권장)

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --image_root mvtec_root/chest_xray/archive `
    --train_csv mvtec_root/chest_xray/archive/train.csv `
    --valid_csv mvtec_root/chest_xray/archive/valid.csv `
    --img_size 320 `
    --batch_size 16 `
    --epochs 50 `
    --learning_rate 1e-4 `
    --device cuda `
    --use_undersampling `
    --use_attention `
    --use_amp
```

### 모든 개선 기능 사용

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --image_root mvtec_root/chest_xray/archive `
    --train_csv mvtec_root/chest_xray/archive/train.csv `
    --valid_csv mvtec_root/chest_xray/archive/valid.csv `
    --img_size 320 `
    --batch_size 16 `
    --epochs 50 `
    --learning_rate 1e-4 `
    --device cuda `
    --use_undersampling `
    --max_samples_per_class 5000 `
    --use_attention `
    --early_stopping_patience 10 `
    --early_stopping_min_delta 0.0001 `
    --use_amp
```

### Command Prompt

```cmd
cd C:\Project\AI
python -m mvtec_root.chest_xray.resnet50_multilabel ^
    --image_root mvtec_root\chest_xray\archive ^
    --train_csv mvtec_root\chest_xray\archive\train.csv ^
    --valid_csv mvtec_root\chest_xray\archive\valid.csv ^
    --img_size 320 ^
    --batch_size 16 ^
    --epochs 50 ^
    --learning_rate 1e-4 ^
    --device cuda ^
    --use_undersampling ^
    --use_attention ^
    --use_amp
```

### Linux / WSL

```bash
cd /mnt/c/Project/AI
python -m mvtec_root.chest_xray.resnet50_multilabel \
  --image_root mvtec_root/chest_xray/archive \
  --train_csv mvtec_root/chest_xray/archive/train.csv \
  --valid_csv mvtec_root/chest_xray/archive/valid.csv \
  --img_size 320 \
  --batch_size 16 \
  --epochs 50 \
  --learning_rate 1e-4 \
  --device cuda \
  --use_undersampling \
  --use_attention \
  --use_amp
```

---

## 4. 주요 인자

### 기본 인자

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--image_root` | 이미지/CSV가 위치한 루트 경로 | `./archive` |
| `--train_csv` | 학습용 CSV 파일 경로 | `./archive/train.csv` |
| `--valid_csv` | 검증용 CSV 파일 경로 | `./archive/valid.csv` |
| `--labels` | 사용할 라벨 목록 (공백으로 구분) | 14개 전체 라벨 |
| `--img_size` | 입력 이미지 해상도 | 320 |
| `--batch_size` | 배치 크기 | 16 |
| `--epochs` | 최대 학습 에폭 수 | **50** (변경됨) |
| `--learning_rate` | AdamW 학습률 | 1e-4 |
| `--weight_decay` | AdamW weight decay | 1e-5 |
| `--num_workers` | DataLoader 워커 수 | 4 |
| `--threshold` | 고정 임계값 (None이면 클래스별 최적화) | None |
| `--device` | 사용할 디바이스 (cuda/cpu) | cuda |
| `--use_amp` | Mixed Precision Training (AMP) 사용 | False |
| `--freeze_backbone` | ResNet 백본 고정 여부 | False |
| `--uncertain_policy` | -1(uncertain) 처리 방식 (zeros/ones) | zeros |
| `--pos_weight_clip` | pos_weight 상한값 | 10.0 |

### 🆕 개선 기능 인자

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--use_attention` | CBAM Attention 사용 | **True** |
| `--no_attention` | Attention 비활성화 | - |
| `--use_undersampling` | 클래스 불균형 해소를 위한 Undersampling | False |
| `--max_samples_per_class` | 클래스당 최대 샘플 수 (None이면 자동) | None |
| `--early_stopping_patience` | Early stopping patience (에폭) | 10 |
| `--early_stopping_min_delta` | Early stopping 최소 개선량 | 1e-4 |

### 출력 경로

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--checkpoint_path` | 체크포인트 저장 경로 | `checkpoints/resnet101_multilabel_best.pt` |
| `--history_path` | 학습 이력 저장 경로 | `classification_results/resnet101_multilabel/history.json` |
| `--thresholds_path` | 최적 임계값 저장 경로 | `classification_results/resnet101_multilabel/optimal_thresholds.json` |

---

## 5. 출력물

### 체크포인트

- **위치**: `checkpoints/resnet101_multilabel_best.pt` (기본값)
- **내용**: 검증 Macro F1이 최고였을 때의 모델 가중치
- **포함 정보**:
  - `model_state_dict`: 모델 가중치
  - `optimizer_state_dict`: 옵티마이저 상태
  - `epoch`: 에폭 번호
  - `metrics`: 최고 성능 지표

### 학습 이력

- **위치**: `classification_results/resnet101_multilabel/history.json` (기본값)
- **내용**: 각 에폭별 학습/검증 지표
- **포함 정보**:
  - `epoch`: 에폭 번호
  - `train_loss`: 학습 손실
  - `train_sample_acc`: 학습 Sample Accuracy
  - `val_loss`: 검증 손실
  - `sample_acc`: 검증 Sample Accuracy
  - `micro_f1`: Micro F1 Score
  - `macro_f1`: Macro F1 Score
  - `macro_auc`: Macro AUC (NaN 가능)
  - `macro_ap`: Macro Average Precision
  - `lr`: 현재 학습률

### 🆕 최적 임계값

- **위치**: `classification_results/resnet101_multilabel/optimal_thresholds.json` (기본값)
- **내용**: 클래스별 최적 임계값 (F1-score 최대화)
- **포함 정보**:
  ```json
  {
    "Atelectasis": 0.423,
    "Cardiomegaly": 0.512,
    ...
  }
  ```
- **사용**: `--threshold`를 지정하지 않으면 자동으로 사용됨

### 콘솔 출력

각 에폭마다 다음 정보가 출력됩니다:
- 학습/검증 손실
- Sample Accuracy
- Micro/Macro F1 Score
- Early Stopping 상태
- 최적 임계값 탐색 진행 상황 (학습 종료 후)

---

## 6. 주요 기능 상세 설명

### 6.1 CBAM Attention Mechanism

**Convolutional Block Attention Module (CBAM)**은 Channel Attention과 Spatial Attention을 순차적으로 적용하여 중요한 특징을 강조합니다.

- **Channel Attention**: 어떤 채널이 중요한지 학습
- **Spatial Attention**: 이미지의 어느 부분이 중요한지 학습
- **효과**: 성능 향상 및 해석 가능성 증가
- **비활성화**: `--no_attention` 플래그 사용

### 6.2 Undersampling

클래스 불균형 문제를 해소하기 위해 다수 클래스의 샘플을 소수 클래스에 맞춰 감소시킵니다.

- **활성화**: `--use_undersampling` 플래그
- **방법**: 각 샘플의 주요 클래스를 식별하고, 클래스별로 균형있게 샘플링
- **최대 샘플 수**: `--max_samples_per_class`로 제한 (None이면 자동 계산)
- **효과**: 소수 클래스 학습 개선

### 6.3 Early Stopping

검증 성능이 더 이상 개선되지 않으면 학습을 조기 종료합니다.

- **Patience**: `--early_stopping_patience` (기본값: 10 에폭)
- **최소 개선량**: `--early_stopping_min_delta` (기본값: 0.0001)
- **효과**: 과적합 방지 및 학습 시간 단축
- **동작**: Macro F1이 `best_f1 + min_delta` 이상이면 최고 모델로 저장

### 6.4 클래스별 최적 임계값 탐색

각 클래스마다 F1-score를 최대화하는 임계값을 자동으로 찾습니다.

- **활성화**: `--threshold`를 지정하지 않으면 자동 활성화
- **방법**: 검증 데이터에서 0.1~0.9 범위를 0.01 단위로 탐색
- **저장**: 학습 종료 후 JSON 파일로 저장
- **사용**: 최종 평가 시 자동으로 적용

---

## 7. 학습 전략

### 손실 함수

- **BCEWithLogitsLoss**: 멀티레이블 분류에 적합한 Binary Cross-Entropy Loss
- **pos_weight**: 클래스 불균형 완화를 위한 가중치 자동 계산
  - `pos_weight = (negative_samples / positive_samples)`로 계산
  - `--pos_weight_clip`으로 상한값 제한 (기본값: 10.0)

### 옵티마이저 및 스케줄러

- **옵티마이저**: AdamW
- **스케줄러**: CosineAnnealingLR
  - 학습률이 코사인 함수 형태로 감소
  - 최종 학습률 = `learning_rate * 0.1`
  - `T_max = epochs`로 설정

### 데이터 증강

- **학습 시**: 
  - Resize
  - RandomHorizontalFlip
  - RandomRotation (7도)
  - **ColorJitter** (밝기/대비 0.1) 🆕
  - Normalize (ImageNet 통계)
- **검증 시**: 
  - Resize
  - Normalize (ImageNet 통계)

### Mixed Precision Training (AMP)

- `--use_amp` 플래그로 활성화
- 메모리 사용량 감소 및 학습 속도 향상
- GPU 메모리가 부족할 때 유용
- ResNet101에서는 특히 권장됨

---

## 8. 평가 지표

### Sample Accuracy

전체 샘플 중 모든 라벨을 정확히 맞춘 샘플의 비율

### Micro F1 Score

모든 라벨의 TP, FP, FN을 합산하여 계산한 F1 Score

### Macro F1 Score

각 라벨별 F1 Score의 평균 (클래스 불균형 고려)

### Macro AUC

각 라벨별 AUC의 평균 (ROC-AUC)
- 일부 클래스에 양성/음성 샘플이 없으면 NaN 반환

### Macro AP

각 라벨별 Average Precision의 평균 (PR-AUC)

---

## 9. 자주 묻는 질문

### Q1. ResNet50과 ResNet101의 차이는?

- **ResNet101**: 더 깊은 네트워크 (101 layers vs 50 layers)
- **성능**: 일반적으로 더 높은 정확도
- **메모리**: 더 많은 GPU 메모리 필요
- **속도**: 학습/추론 속도는 약간 느림

### Q2. Attention을 사용하지 않아도 되나요?

`--no_attention` 플래그로 비활성화할 수 있습니다:
```powershell
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --no_attention `
    --use_undersampling
```

### Q3. Undersampling은 언제 사용하나요?

클래스 불균형이 심할 때 사용하세요:
- 한 클래스가 다른 클래스보다 훨씬 많은 경우
- 소수 클래스의 성능이 매우 낮은 경우
- `--use_undersampling` 플래그로 활성화

### Q4. Early Stopping은 어떻게 동작하나요?

- `--early_stopping_patience` 에폭 동안 개선이 없으면 학습 중단
- 최고 성능 모델은 자동으로 저장됨
- 과적합을 방지하고 학습 시간을 단축

### Q5. 최적 임계값은 언제 찾나요?

- 학습이 완료된 후 (또는 Early Stopping 후)
- 검증 데이터에서 자동으로 탐색
- `--threshold`를 지정하면 고정 임계값 사용 (최적화 안 함)

### Q6. GPU 메모리가 부족해요.

다음 방법을 시도해보세요:
1. `--batch_size`를 줄이기 (예: 16 → 8)
2. `--img_size`를 줄이기 (예: 320 → 224)
3. `--use_amp` 사용 (필수)
4. `--freeze_backbone` 사용 (백본 고정, 분류기만 학습)
5. `--use_attention` 비활성화 (`--no_attention`)

### Q7. 학습 속도를 높이고 싶어요.

1. `--use_amp` 사용
2. `--num_workers` 증가 (CPU 코어 수에 맞게)
3. `--batch_size` 증가 (GPU 메모리 허용 범위 내)
4. `--use_undersampling` 사용 (학습 데이터 감소)
5. `--early_stopping_patience` 감소 (더 빨리 종료)

### Q8. 특정 라벨만 학습하고 싶어요.

`--labels` 옵션으로 원하는 라벨만 지정할 수 있습니다:

```powershell
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --labels "Atelectasis" "Cardiomegaly" "Pneumonia" `
    --train_csv mvtec_root/chest_xray/archive/train.csv `
    --valid_csv mvtec_root/chest_xray/archive/valid.csv
```

---

## 10. 빠른 점검 체크리스트

- [ ] `archive/train.csv`, `archive/valid.csv` 파일 존재 확인
- [ ] CSV 파일의 `Path` 컬럼이 올바른 이미지 경로를 가리키는지 확인
- [ ] 이미지 파일들이 실제로 존재하는지 확인
- [ ] GPU 메모리 모니터링 (nvidia-smi)
- [ ] `classification_results/resnet101_multilabel/history.json`으로 학습 진행 상황 확인
- [ ] `checkpoints/resnet101_multilabel_best.pt` 체크포인트 저장 확인
- [ ] `classification_results/resnet101_multilabel/optimal_thresholds.json` 최적 임계값 확인

---

## 11. 예제 실행

### 기본 실행 (모든 개선 기능 적용)

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --image_root mvtec_root/chest_xray/archive `
    --train_csv mvtec_root/chest_xray/archive/train.csv `
    --valid_csv mvtec_root/chest_xray/archive/valid.csv `
    --use_undersampling `
    --use_attention `
    --use_amp
```

### 최소 설정 (빠른 테스트)

```powershell
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --epochs 5 `
    --batch_size 8 `
    --img_size 224 `
    --use_amp
```

### 고급 설정 (최대 성능)

```powershell
python -m mvtec_root.chest_xray.resnet50_multilabel `
    --image_root mvtec_root/chest_xray/archive `
    --train_csv mvtec_root/chest_xray/archive/train.csv `
    --valid_csv mvtec_root/chest_xray/archive/valid.csv `
    --img_size 320 `
    --batch_size 16 `
    --epochs 50 `
    --learning_rate 1e-4 `
    --weight_decay 1e-5 `
    --num_workers 8 `
    --device cuda `
    --use_undersampling `
    --max_samples_per_class 5000 `
    --use_attention `
    --early_stopping_patience 10 `
    --early_stopping_min_delta 0.0001 `
    --use_amp `
    --uncertain_policy zeros `
    --pos_weight_clip 10.0
```

---

## 12. 모델 구조

### ResNet101WithAttention

```
Input Image (3, 320, 320)
  ↓
ResNet101 Backbone
  ├─ Conv1 + BN + ReLU + MaxPool
  ├─ Layer1 (3 blocks)
  ├─ Layer2 (4 blocks)
  ├─ Layer3 (23 blocks)
  ├─ Layer4 (3 blocks)
  ↓
CBAM Attention (Channel + Spatial) 🆕
  ↓
Global Average Pooling
  ↓
Classification Head
  ├─ Dropout(0.3)
  ├─ Linear(2048 → 512)
  ├─ ReLU
  ├─ Dropout(0.2)
  └─ Linear(512 → num_classes)
  ↓
Output (num_classes)
```

---

## 참고

- 본 스크립트는 CheXpert 데이터셋 형식을 기반으로 합니다.
- ResNet101은 ImageNet 사전학습 가중치를 사용합니다.
- 멀티레이블 분류이므로 한 이미지에 여러 질병이 동시에 존재할 수 있습니다.
- 클래스 불균형이 심하므로 `pos_weight`가 자동으로 계산되어 적용됩니다.
- 개선 버전은 클래스 불균형 문제를 해결하기 위해 다양한 기법을 적용했습니다.

---

## 변경 이력

### v2.0 (개선 버전)
- ResNet50 → ResNet101 변경
- CBAM Attention 추가
- Undersampling 기능 추가
- Early Stopping 구현
- 클래스별 최적 임계값 탐색 추가
- 에폭 기본값 10 → 50 변경
- 체크포인트 경로 변경 (resnet50 → resnet101)

### v1.0 (초기 버전)
- ResNet50 기반 멀티레이블 분류
- 기본 학습 전략

문의사항은 언제든지 공유해 주세요. 지속적인 개선을 위한 피드백을 환영합니다!
