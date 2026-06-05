# 의료 영상 이상 탐지 시스템

의료 영상(JPG/PNG)을 위한 비지도 이상 탐지 시스템입니다. 정상 이미지만으로 학습하여 질병이나 결함을 자동으로 탐지합니다.

## 주요 기능

1. **Autoencoder 기반 이상 탐지**: 복원 오차를 이용한 이상 탐지 및 히트맵 생성
2. **Dual Anomaly 모델**: Reconstruction + Feature Attention을 결합한 고급 이상 탐지 모델
3. **MVTec AD 형식 변환**: 임의의 폴더 구조를 MVTec 표준 구조로 자동 변환
4. **의료 친화적 데이터 증강**: 수평 플립, 소각도 회전, CLAHE, 가우시안 노이즈 등
5. **모델 평가 시스템**: 추론 결과를 실제 라벨과 비교하여 성능 평가 (ROC-AUC, PR-AUC, F1-Score 등)

---

## 환경 설정

### 가상환경 설정 (권장)

프로젝트를 격리된 환경에서 실행하기 위해 Python 가상환경을 사용하는 것을 강력히 권장합니다.

#### 1. 가상환경 생성

**macOS/Linux:**
```bash
# Python 3.8 이상 버전이 설치되어 있어야 합니다
python3 -m venv venv

# 또는 특정 Python 버전 지정
python3.10 -m venv venv
```

**Windows:**
```bash
# Python 3.8 이상 버전이 설치되어 있어야 합니다
python -m venv venv

# 또는 특정 Python 버전 지정
py -3.10 -m venv venv
```

#### 2. 가상환경 활성화

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

가상환경이 활성화되면 터미널 프롬프트 앞에 `(venv)`가 표시됩니다.

#### 3. pip 업그레이드 (선택사항)

```bash
pip install --upgrade pip
```

#### 4. 패키지 설치

```bash
# requirements.txt를 사용한 설치 (권장)
pip install -r requirements.txt

# 또는 개별 설치
pip install torch torchvision numpy pillow matplotlib tqdm scikit-image
```

#### 5. 가상환경 비활성화

작업이 끝난 후 가상환경을 비활성화하려면:
```bash
deactivate
```

### 필수 패키지 설치 (가상환경 없이)

가상환경을 사용하지 않는 경우:

```bash
pip install -r requirements.txt
```

또는 개별 설치:
```bash
pip install torch torchvision numpy pillow matplotlib tqdm scikit-image
```

### GPU 사용 (선택사항)

CUDA가 설치된 환경에서는 자동으로 GPU를 사용합니다. CPU만 사용 가능한 환경에서도 동작합니다.

**CUDA 지원 PyTorch 설치 (GPU 사용 시):**

CUDA가 설치된 시스템에서 GPU를 사용하려면, [PyTorch 공식 웹사이트](https://pytorch.org/get-started/locally/)에서 CUDA 버전에 맞는 설치 명령어를 확인하세요.

예시 (CUDA 11.8):
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

예시 (CUDA 12.1):
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 데이터셋 구성 방법

### 방법 1: MVTec AD 형식으로 직접 구성

MVTec AD 표준 형식으로 데이터를 구성합니다:

```
mvtec_root/
  chest_xray/                 # 카테고리명 (예: chest_xray, brain_mri 등)
    train/
      good/                   # 정상 이미지 (학습용)
        image001.jpg
        image002.png
        ...
    test/
      good/                   # 정상 이미지 (테스트용, 선택사항)
        test_normal_001.jpg
        ...
      pneumonia/              # 이상 이미지 (테스트용)
        anomaly_001.jpg
        anomaly_002.png
        ...
      # 추가 이상 타입들...
      # tuberculosis/
      # ...
    ground_truth/             # 픽셀 단위 마스크 (선택사항)
      pneumonia/
        anomaly_001_mask.png
        ...
```

**구성 단계:**

1. **카테고리 폴더 생성**
   ```bash
   mkdir -p mvtec_root/chest_xray/{train/good,test/good,test/pneumonia,ground_truth/pneumonia}
   ```

2. **정상 이미지 배치**
   - 학습용 정상 이미지를 `train/good/` 폴더에 복사
   - 테스트용 정상 이미지를 `test/good/` 폴더에 복사 (선택)

3. **이상 이미지 배치**
   - 각 이상 타입별로 폴더를 만들어 `test/` 아래에 배치
   - 예: `test/pneumonia/`, `test/tuberculosis/` 등

4. **Ground Truth 마스크 배치 (선택)**
   - 픽셀 단위 마스크가 있다면 `ground_truth/<이상타입>/` 폴더에 배치
   - 마스크 파일명은 원본 이미지와 매칭되어야 함

### 방법 2: 기존 데이터를 MVTec 형식으로 변환

기존에 다른 구조로 되어 있는 데이터를 자동으로 변환할 수 있습니다.

**지원되는 입력 구조:**

```
my_med_images/
  train/
    normal/                   # 정상 이미지
      img1.jpg
      ...
  test/
    normal/                   # 테스트용 정상 이미지 (선택)
      test1.jpg
      ...
    anomaly/                  # 옵션 1: anomaly 폴더 안에 이상 타입별 폴더
      pneumonia/
        img1.jpg
        ...
      tuberculosis/
        ...
    # 또는
    pneumonia/                # 옵션 2: test 폴더 바로 아래 이상 타입 폴더
      images/                 # (선택) images 서브폴더
        img1.jpg
      masks/                  # (선택) masks 서브폴더
        img1_mask.png
    ground_truth/             # 옵션 3: 별도 ground_truth 폴더
      pneumonia/
        img1_mask.png
        ...
```

**변환 명령어:**

```bash
python -m mvtec_root.chest_xray.anomaly.main \
  --mode convert_to_mvtec \
  --data_root ./my_med_images \
  --mvtec_out ./mvtec_medical \
  --category chest_xray
```

변환 후 `mvtec_medical/chest_xray/` 폴더에 MVTec 형식으로 구성됩니다.

---

## 모델 학습 방법

### 0단계: 데이터 준비 (CheXpert → MVTec 변환)

CheXpert 형식의 데이터를 MVTec 형식으로 변환합니다.

```bash
# Windows
python convert_chexpert_to_mvtec.py

# 또는 직접 실행
python convert_chexpert_to_mvtec.py
```

변환 후 다음 구조로 데이터가 준비됩니다:
```
mvtec_root/chest_xray/
  train/
    good/          # 정상 이미지 (학습용)
  test/
    good/          # 정상 이미지 (테스트용)
    pneumonia/     # 이상 이미지 (질병별)
    ...
```

### 1단계: Autoencoder 학습

Autoencoder는 정상 이미지만으로 학습하여 복원 오차를 최소화합니다.

#### 기본 학습 명령어 (최소 옵션)

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode train_autoencoder --data_root ./mvtec_root/chest_xray --epochs 30 --batch_size 16 --img_size 256 --checkpoint_dir ./checkpoints

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_autoencoder \
  --data_root ./mvtec_root/chest_xray \
  --epochs 30 \
  --batch_size 16 \
  --img_size 256 \
  --checkpoint_dir ./checkpoints
```

#### 권장 학습 명령어 (데이터 증강 + CLAHE 포함)

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode train_autoencoder --data_root ./mvtec_root/chest_xray --epochs 30 --batch_size 16 --img_size 256 --lr 0.001 --aug --clahe --noise_sigma 0.01 --checkpoint_dir ./checkpoints --num_workers 4 --seed 42

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_autoencoder \
  --data_root ./mvtec_root/chest_xray \
  --epochs 30 \
  --batch_size 16 \
  --img_size 256 \
  --lr 0.001 \
  --aug \                    # 데이터 증강 활성화
  --clahe \                  # CLAHE 대비 보정 사용
  --noise_sigma 0.01 \       # 가우시안 노이즈 추가
  --checkpoint_dir ./checkpoints \
  --num_workers 4 \
  --seed 42
```

#### 빠른 테스트용 학습 (에포크 수 감소)

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode train_autoencoder --data_root ./mvtec_root/chest_xray --epochs 5 --batch_size 32 --img_size 256 --checkpoint_dir ./checkpoints

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_autoencoder \
  --data_root ./mvtec_root/chest_xray \
  --epochs 5 \
  --batch_size 32 \
  --img_size 256 \
  --checkpoint_dir ./checkpoints
```

#### 주요 파라미터 설명

| 파라미터 | 설명 | 기본값 | 권장값 |
|---------|------|--------|--------|
| `--mode` | 실행 모드 (`train_autoencoder`) | 필수 | `train_autoencoder` |
| `--data_root` | 데이터 루트 경로 | 필수 | `./mvtec_root/chest_xray` |
| `--epochs` | 학습 에포크 수 | 30 | 30-50 |
| `--batch_size` | 배치 크기 | 16 | 16-32 (GPU 메모리에 따라) |
| `--img_size` | 이미지 크기 | 256 | 256 또는 512 |
| `--lr` | 학습률 | 0.001 | 0.001-0.0001 |
| `--aug` | 데이터 증강 활성화 | False | 권장 (의료 영상에 유용) |
| `--clahe` | CLAHE 대비 보정 | False | 권장 (X-ray 영상에 유용) |
| `--noise_sigma` | 가우시안 노이즈 표준편차 | 0.0 | 0.01 (0.0이면 사용 안 함) |
| `--checkpoint_dir` | 체크포인트 저장 디렉토리 | `./checkpoints` | `./checkpoints` |
| `--num_workers` | 데이터 로더 워커 수 | 4 | 4-8 (CPU 코어 수에 따라) |
| `--seed` | 랜덤 시드 | 42 | 42 (재현성) |

#### 학습 결과

- **체크포인트 위치**: `checkpoint_dir/ae_best.pt`
- **저장 내용**: 최고 성능 모델의 가중치, 학습 파라미터, 에포크 정보
- **모니터링**: 학습 중 각 에포크의 MAE(Mean Absolute Error)가 콘솔에 출력됩니다

#### 학습 시간 예상

- **데이터**: 약 18,000개 정상 이미지
- **하드웨어별 예상 시간**:
  - GPU (NVIDIA): 약 1-2시간 (30 에포크)
  - CPU만: 약 10-20시간 (30 에포크)

### 2단계: Dual Anomaly 모델 학습 (선택사항)

Dual Anomaly 모델은 Autoencoder의 복원 오차와 Feature Attention을 결합한 고급 이상 탐지 모델입니다. Autoencoder 학습 후 추가로 학습할 수 있습니다.

#### Dual Anomaly 학습 명령어

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode train_dual --data_root ./mvtec_root/chest_xray --epochs 20 --batch_size 16 --img_size 256 --lr 0.0005 --aug --clahe --noise_sigma 0.01 --checkpoint_dir ./checkpoints --num_workers 4 --seed 42

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_dual \
  --data_root ./mvtec_root/chest_xray \
  --epochs 20 \
  --batch_size 16 \
  --img_size 256 \
  --lr 0.0005 \
  --aug \
  --clahe \
  --noise_sigma 0.01 \
  --checkpoint_dir ./checkpoints \
  --num_workers 4 \
  --seed 42
```

#### 주요 파라미터 설명

| 파라미터 | 설명 | 기본값 | 권장값 |
|---------|------|--------|--------|
| `--mode` | 실행 모드 (`train_dual`) | 필수 | `train_dual` |
| `--epochs` | 학습 에포크 수 | 20 | 20-30 |
| `--lr` | 학습률 | 0.0005 | 0.0005-0.001 |
| `--freeze_ae` | Autoencoder 가중치 고정 | False | 선택사항 (AE를 고정하고 attention만 학습) |
| 기타 파라미터는 Autoencoder와 동일 | | | |

추가로 Dual branch 간 출력을 정렬하는 `--consistency_weight` 옵션(기본 0.05)을 통해 Reconstruction/Feature 브랜치가 정상 데이터에서 유사한 응답을 내도록 규제할 수 있습니다. 값이 높을수록 두 브랜치의 분산을 더 강하게 억제합니다.

#### 학습 결과

- **체크포인트 위치**: `checkpoint_dir/dual_best.pt`
- **사전 요구사항**: `ae_best.pt`가 있어야 함 (없으면 처음부터 학습)
- **학습 방식**: Autoencoder 가중치를 로드한 후 Dual 모델 전체를 학습

---

## 추론 (Inference) 방법

### Autoencoder 추론

학습된 Autoencoder로 테스트 이미지의 이상 점수와 히트맵을 생성합니다.

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode infer_autoencoder --data_root ./mvtec_root/chest_xray --checkpoint ./checkpoints/ae_best.pt --out_dir ./outs_ae --img_size 256 --clahe

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_autoencoder \
  --data_root ./mvtec_root/chest_xray \
  --checkpoint ./checkpoints/ae_best.pt \
  --out_dir ./outs_ae \
  --img_size 256 \
  --clahe
```

**출력 결과:**

- `out_dir/` 폴더에 다음 파일들이 생성됩니다:
  - `{인덱스}_label{라벨}_score{점수}_input.png`: 원본 이미지
  - `{인덱스}_label{라벨}_score{점수}_recon.png`: 복원된 이미지
  - `{인덱스}_label{라벨}_score{점수}_err.png`: 복원 오차 맵
  - `{인덱스}_label{라벨}_score{점수}_overlay.png`: 오차 맵 오버레이
  - `ae_scores.json`: 모든 이미지의 이상 점수 JSON 파일

### Dual Anomaly 추론

학습된 Dual Anomaly 모델로 테스트 이미지의 이상 점수와 히트맵을 생성합니다.

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode infer_dual --data_root ./mvtec_root/chest_xray --checkpoint ./checkpoints/dual_best.pt --out_dir ./outs_dual --img_size 256 --clahe --test_limit_per_class 100

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_dual \
  --data_root ./mvtec_root/chest_xray \
  --checkpoint ./checkpoints/dual_best.pt \
  --out_dir ./outs_dual \
  --img_size 256 \
  --clahe \
  --test_limit_per_class 100
```

**출력 결과:**

- `out_dir/` 폴더에 다음 파일들이 생성됩니다:
  - `{인덱스}_label{라벨}_score{점수}_input.png`: 원본 이미지
  - `{인덱스}_label{라벨}_score{점수}_recon.png`: 복원된 이미지
  - `{인덱스}_label{라벨}_score{점수}_score.png`: 최종 이상 점수 맵
  - `{인덱스}_label{라벨}_score{점수}_s_recon.png`: 복원 기반 점수 맵
  - `{인덱스}_label{라벨}_score{점수}_s_feat.png`: 특징 기반 점수 맵
  - `{인덱스}_label{라벨}_score{점수}_overlay.png`: 히트맵 오버레이
  - `dual_scores.json`: 모든 이미지의 이상 점수 JSON 파일

**추가 옵션:**

- `--test_limit_per_class`: 각 클래스별 최대 샘플 수 제한 (0이면 제한 없음, 기본값: 0)

---

## 전체 워크플로우 예제

### 예제 1: 처음부터 끝까지 (Autoencoder)

```bash
# 1. 데이터 변환 (필요한 경우)
python -m mvtec_root.chest_xray.anomaly.main \
  --mode convert_to_mvtec \
  --data_root ./my_med_images \
  --mvtec_out ./mvtec_medical \
  --category chest_xray

# 2. Autoencoder 학습
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_autoencoder \
  --data_root ./mvtec_medical/chest_xray \
  --epochs 30 \
  --batch_size 16 \
  --img_size 256 \
  --aug \
  --clahe \
  --noise_sigma 0.01

# 3. 추론
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_autoencoder \
  --data_root ./mvtec_medical/chest_xray \
  --checkpoint ./checkpoints/ae_best.pt \
  --out_dir ./outs_ae \
  --clahe
```

### 예제 2: Dual Anomaly 모델 (고급)

```bash
# 1. Autoencoder 학습 (사전 요구사항)
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_autoencoder \
  --data_root ./mvtec_root/chest_xray \
  --epochs 30 \
  --batch_size 16 \
  --img_size 256 \
  --aug \
  --clahe \
  --noise_sigma 0.01 \
  --checkpoint_dir ./checkpoints

# 2. Dual Anomaly 모델 학습
python -m mvtec_root.chest_xray.anomaly.main \
  --mode train_dual \
  --data_root ./mvtec_root/chest_xray \
  --epochs 20 \
  --batch_size 16 \
  --img_size 256 \
  --lr 0.0005 \
  --aug \
  --clahe \
  --noise_sigma 0.01 \
  --checkpoint_dir ./checkpoints

# 3. Dual Anomaly 추론
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_dual \
  --data_root ./mvtec_root/chest_xray \
  --checkpoint ./checkpoints/dual_best.pt \
  --out_dir ./outs_dual \
  --img_size 256 \
  --clahe \
  --test_limit_per_class 100

# 4. 모델 평가
python -m mvtec_root.chest_xray.anomaly.main \
  --mode evaluate \
  --json_path ./outs_dual/dual_scores.json \
  --out_dir ./evaluation_results \
  --model_name DualAnomaly \
  --class_names good pneumonia tuberculosis
```

---

## 모델 평가

추론 결과를 실제 라벨과 비교하여 모델 성능을 평가할 수 있습니다.

### 필수 패키지 설치

평가 기능을 사용하려면 다음 패키지가 필요합니다:

```bash
pip install scikit-learn matplotlib seaborn
```

### 평가 실행

```bash
# Windows
python -m mvtec_root.chest_xray.anomaly.main --mode evaluate --json_path ./outs_dual/dual_scores.json --out_dir ./evaluation_results --model_name DualAnomaly --class_names good pneumonia tuberculosis

# Linux/macOS
python -m mvtec_root.chest_xray.anomaly.main \
  --mode evaluate \
  --json_path ./outs_dual/dual_scores.json \
  --out_dir ./evaluation_results \
  --model_name DualAnomaly \
  --class_names good pneumonia tuberculosis
```

**파라미터 설명:**

- `--json_path`: 평가할 추론 결과 JSON 파일 경로 (필수)
  - Autoencoder: `ae_scores.json`
  - Dual Anomaly: `dual_scores.json`
- `--out_dir`: 평가 결과 저장 디렉토리
- `--model_name`: 모델 이름 (결과 파일에 표시)
- `--class_names`: 클래스 이름 리스트 (선택, 예: `good pneumonia tuberculosis`)
  - 제공하지 않으면 `class_0`, `class_1` 등으로 표시됩니다

### 평가 결과

평가 실행 후 `out_dir`에 다음 파일들이 생성됩니다:

1. **`evaluation_results.json`**: 모든 평가 메트릭의 상세 결과 (JSON 형식)
2. **`evaluation_report.txt`**: 평가 결과 요약 (텍스트 형식)
3. **`roc_curve.png`**: ROC 곡선 시각화
4. **`pr_curve.png`**: Precision-Recall 곡선 시각화
5. **`confusion_matrix.png`**: 혼동 행렬 시각화
6. **`score_distribution.png`**: 정상/이상 클래스별 점수 분포 히스토그램

### 평가 메트릭

**이진 분류 평가 (정상 vs 이상):**

- **ROC-AUC**: Receiver Operating Characteristic 곡선 아래 면적 (0~1, 높을수록 좋음)
- **PR-AUC**: Precision-Recall 곡선 아래 면적 (0~1, 높을수록 좋음)
- **Accuracy**: 정확도
- **Precision**: 정밀도 (이상으로 예측한 것 중 실제 이상인 비율)
- **Recall**: 재현율 (실제 이상 중 올바르게 탐지한 비율)
- **F1-Score**: Precision과 Recall의 조화 평균
- **최적 Threshold**: Youden's J 통계량으로 찾은 최적 임계값

**다중 클래스 평가 (각 질병별):**

각 질병 클래스에 대해 One-vs-Rest 방식으로 평가:
- ROC-AUC, PR-AUC
- Precision, Recall, F1-Score
- 샘플 수

### 평가 결과 예시

```json
{
  "model_name": "DualAnomaly",
  "binary_classification": {
    "roc_auc": 0.9234,
    "pr_auc": 0.8765,
    "accuracy": 0.8901,
    "precision": 0.8543,
    "recall": 0.8123,
    "f1": 0.8328,
    "threshold": 0.0456
  },
  "multiclass_classification": {
    "good": {
      "roc_auc": 0.9123,
      "pr_auc": 0.8654,
      "n_samples": 150
    },
    "pneumonia": {
      "roc_auc": 0.9456,
      "pr_auc": 0.9012,
      "n_samples": 100
    }
  }
}
```

---

## 결과 해석

### 이상 점수 (Anomaly Score)

- **Autoencoder**: 복원 오차의 평균값 (낮을수록 정상, 높을수록 이상)
- **Dual Anomaly**: 복원 오차와 특징 attention을 결합한 점수의 상위 1% 평균값 (낮을수록 정상, 높을수록 이상)

### 히트맵

- 빨간색/노란색 영역: 이상 가능성이 높은 영역
- 파란색/어두운 영역: 정상으로 보이는 영역

### JSON 결과 파일

각 추론 모드에서 생성되는 JSON 파일에는 다음과 같은 정보가 포함됩니다:

```json
[
  {
    "idx": 0,
    "label": 0,
    "score": 0.0234
  },
  {
    "idx": 1,
    "label": 1,
    "score": 0.1567
  }
]
```

- `idx`: 이미지 인덱스
- `label`: 클래스 라벨 (0: 정상, 1 이상: 이상)
- `score`: 이상 점수

---

## 팁 및 주의사항

1. **데이터셋 크기**: 정상 이미지는 최소 100장 이상 권장
2. **이미지 크기**: `img_size`는 GPU 메모리에 따라 조정 (256, 512 등)
3. **배치 크기**: GPU 메모리가 부족하면 `batch_size`를 줄이세요
4. **CLAHE 사용**: 의료 영상의 대비가 낮은 경우 `--clahe` 옵션 권장
5. **데이터 증강**: 정상 데이터가 적을 때 `--aug` 옵션 사용 권장
6. **Dual Anomaly 모델**: Autoencoder보다 일반적으로 더 정확하지만 학습 시간이 더 걸립니다
7. **테스트 데이터 제한**: 대용량 테스트 데이터의 경우 `--test_limit_per_class` 옵션으로 샘플 수를 제한할 수 있습니다

---

## 문제 해결

### GPU 메모리 부족

- `batch_size`를 줄이세요 (예: 16 → 8)
- `img_size`를 줄이세요 (예: 256 → 224)
- `num_workers`를 줄이세요 (예: 4 → 2)

### 학습이 수렴하지 않음

- 학습률(`--lr`)을 조정하세요
- 에포크 수를 늘리세요
- 데이터 증강을 활성화하세요 (`--aug`)

### 결과가 좋지 않음

- CLAHE 사용을 시도하세요 (`--clahe`)
- Dual Anomaly 모델을 사용해보세요 (Autoencoder보다 성능이 좋을 수 있음)
- 더 많은 정상 이미지로 학습하세요
- 데이터 증강을 활성화하세요 (`--aug`)
- 학습률과 에포크 수를 조정하세요

---

## 라이선스

이 프로젝트는 연구 및 교육 목적으로 제공됩니다.
