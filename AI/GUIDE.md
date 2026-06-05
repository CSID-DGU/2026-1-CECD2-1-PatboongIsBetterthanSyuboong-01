# Dual Branch Anomaly Detection - 팀원 가이드

이 가이드는 **학습된 모델을 사용하여 추론만 수행**하는 방법을 안내합니다. 모델 학습 없이 바로 이상 탐지를 실행할 수 있습니다.

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [사전 요구사항](#사전-요구사항)
3. [환경 설정](#환경-설정)
4. [데이터셋 준비](#데이터셋-준비)
5. [추론 실행](#추론-실행)
6. [결과 확인](#결과-확인)
7. [문제 해결](#문제-해결)

---

## 프로젝트 개요

이 프로젝트는 **의료 영상(X-ray) 이상 탐지 시스템**입니다. 정상 이미지만으로 학습된 모델을 사용하여 질병이나 결함을 자동으로 탐지합니다.

### 주요 특징

- ✅ **학습된 모델 제공**: `checkpoints/` 디렉토리에 사전 학습된 모델 포함
- ✅ **Dual Branch 구조**: Reconstruction + Feature Attention 결합
- ✅ **Outlier 처리**: Robust statistics 기반 스코어 계산
- ✅ **히트맵 시각화**: 이상 영역을 시각적으로 표시

### 프로젝트 구조

```
프로젝트 루트/
├── checkpoints/              # 학습된 모델 (이미 포함됨)
│   ├── dual_best.pt         # Dual Branch 모델 (추론에 사용)
│   └── ae_best.pt           # Autoencoder 모델
├── mvtec_root/
│   └── chest_xray/          # 데이터셋 및 코드
│       ├── main.py          # 메인 실행 파일
│       ├── inference.py     # 추론 코드
│       └── ...
├── convert_chexpert_to_mvtec.py  # 데이터셋 변환 스크립트
└── GUIDE.md                 # 이 파일
```

---


## 데이터셋 준비

### 1단계: CheXpert 데이터셋 다운로드

#### 방법 : 수동 다운로드

1. [CheXpert 데이터셋 페이지](https://www.kaggle.com/datasets/ashery/chexpert) 접속
2. "Download" 버튼 클릭
3. 다운로드된 `chexpert.zip` 파일 압축 해제
4. `chexpert_data/` 디렉토리에 저장

### 2단계: 데이터셋 구조 확인

다운로드 후 다음과 같은 구조가 있어야 합니다:

```
chexpert_data/
├── archive/
│   ├── train.csv, valid.csv
│   └── train/, valid/          # AP/PA, Lateral 이미지 포함
```

### 3단계: PA + ROI 마스킹 세트 생성 (필수)

모든 학습·추론 전에 **PA/Frontal 이미지만 남기고, 폐/심장 ROI 외부를 마스킹**합니다.  
CheXmask-Database-main 기반 `roi_mask_pipeline.py` 를 실행하여 새로운 `archive_pa` 루트를 생성하세요.

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.segmentation_processing.roi_mask_pipeline `
    --source_root mvtec_root/chest_xray/archive `
    --target_root mvtec_root/chest_xray/archive_pa `
    --device cpu `
    --skip-existing
```

#### 파이프라인 주요 기능
- CheXpert CSV에서 **Frontal + PA 뷰**만 필터링
- HybridGNet 모델(출처: CheXmask-Database-main)로 폐·심장 분할 → 환자 외부 마스킹
- `archive_pa/train.csv`, `archive_pa/valid.csv` 재생성
- 이후 분류·추론 스크립트의 기본 경로는 모두 `archive_pa`로 설정됨

> ⚠️ 처음 실행할 때는 PyG CUDA 의존성 이슈를 피하기 위해 `--device cpu`를 권장합니다. GPU를 쓰려면 torch-geometric 2.4.0(+CUDA12.1) wheel을 설치해 주세요.

> ⚠️ `archive_pa` 생성이 끝나야 `resnet50_multilabel.py` 등 다운스트림 코드가 정상 동작합니다.

### 4단계: (선택) MVTec 형식 변환

Dual Branch 이상탐지 실험을 위해서는 ROI 마스킹된 CSV를 기반으로 다시 MVTec 구조를 생성해야 합니다.  
`convert_chexpert_to_mvtec.py`의 기본 경로는 이미 `archive_pa`를 가리키도록 수정돼 있으므로 아래 명령만 실행하면 됩니다.

```powershell
cd C:\Project\AI
python convert_chexpert_to_mvtec.py
```

이 명령은 `mvtec_root/chest_xray/train`, `mvtec_root/chest_xray/test`를 재생성합니다. (필요 시 기존 폴더는 자동으로 덮어쓰거나 미리 삭제하세요.)

---

## Autoencoder 학습

ROI 마스킹 및 MVTec 변환이 끝났다면 Autoencoder를 먼저 학습해 두는 것이 좋습니다. 학습된 AE는 Dual Branch 모델의 Reconstruction branch에서 재사용됩니다.

### 1. 학습 명령

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_autoencoder `
    --data_root mvtec_root/chest_xray `
    --checkpoint_dir checkpoints `
    --epochs 50 `
    --stability_weight 0.05 `
    --stability_target 0.05 `
    --clahe --aug --noise_sigma 0.01 `
    --batch_size 16 `
    --img_size 256 `
    --num_workers 4 `
    --device cuda
```

- `--data_root`: ROI 기반 MVTec 구조 (`mvtec_root/chest_xray`).
- `--checkpoint_dir`: 결과가 저장될 위치 (`checkpoints/ae_best.pt`).
- GPU가 없다면 `--device cpu`로 변경.

### 2. 로그 및 결과
- 진행 상황은 콘솔 로그와 `checkpoints/` 내 모델 파일로 확인할 수 있습니다.
- 학습이 끝나면 `ae_best.pt`가 Dual Branch 학습/추론에서 사용됩니다.

> ⚠️ 이미 학습된 `ae_best.pt`가 있다면 이 단계를 건너뛰어도 됩니다.

---

## 추론 실행

### 1단계: 체크포인트 확인

`checkpoints/` 디렉토리에 다음 파일이 있는지 확인하세요:

- `dual_best.pt` - Dual Branch 모델 (추론에 사용)
- `ae_best.pt` - Autoencoder 모델 (선택사항)

### 2단계: 추론 명령어 실행

#### 기본 추론 (모든 테스트 데이터) 추천X 컴퓨터 멈춰요;;

**Windows:**
```bash
python mvtec_root\chest_xray\main.py --mode infer_dual --data_root mvtec_root/chest_xray --checkpoint checkpoints/dual_best.pt --out_dir outs_dual --img_size 256 --num_workers 4
```

**Linux/macOS:**
```bash
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_dual \
  --data_root mvtec_root/chest_xray \
  --checkpoint checkpoints/dual_best.pt \
  --out_dir outs_dual \
  --img_size 256 \
  --num_workers 4
```

#### 제한된 추론 (각 클래스별 최대 N개만)

테스트 시간을 단축하려면 각 클래스별로 제한할 수 있습니다:

**Windows:**
```bash
python mvtec_root\chest_xray\main.py --mode infer_dual --data_root mvtec_root/chest_xray --checkpoint checkpoints/dual_best.pt --out_dir outs_dual --img_size 256 --num_workers 4 --test_limit_per_class 10
```

**Linux/macOS:**
```bash
python -m mvtec_root.chest_xray.anomaly.main \
  --mode infer_dual \
  --data_root mvtec_root/chest_xray \
  --checkpoint checkpoints/dual_best.pt \
  --out_dir outs_dual \
  --img_size 256 \
  --num_workers 4 \
  --test_limit_per_class 10
```

### 3단계: 주요 파라미터 설명

| 파라미터 | 설명 | 기본값 | 필수 여부 |
|---------|------|--------|----------|
| `--mode` | 실행 모드 | - | ✅ 필수 (`infer_dual`) |
| `--data_root` | 데이터 루트 경로 | - | ✅ 필수 |
| `--checkpoint` | 체크포인트 파일 경로 | - | ✅ 필수 |
| `--out_dir` | 결과 출력 디렉토리 | `./outs` | ❌ 선택 |
| `--img_size` | 이미지 크기 | 256 | ❌ 선택 |
| `--num_workers` | 데이터 로더 워커 수 | 4 | ❌ 선택 |
| `--test_limit_per_class` | 클래스별 최대 샘플 수 | 0 (제한 없음) | ❌ 선택 |
| `--clahe` | CLAHE 대비 보정 사용 | False | ❌ 선택 |

### 4단계: 실행 예시

```bash
# Windows 예시
python mvtec_root\chest_xray\main.py --mode infer_dual --data_root mvtec_root/chest_xray --checkpoint checkpoints/dual_best.pt --out_dir outs_dual --img_size 256 --num_workers 4 --test_limit_per_class 50

# 실행 중 출력 예시:
# [INFO] 모델 threshold 사용: 3.163980e-09
# [Dual Infer]: 100%|████████████| 500/500 [02:30<00:00,  3.33it/s]
# Saved results to outs_dual
```

---

## 결과 확인

### 1. 출력 디렉토리 구조

추론이 완료되면 `outs_dual/` 디렉토리에 다음 파일들이 생성됩니다:

```
outs_dual/
├── dual_scores.json        # 모든 이미지의 스코어 (중요!)
├── 00000_label0_score3.76e-09_input.png
├── 00000_label0_score3.76e-09_recon.png
├── 00000_label0_score3.76e-09_score.png      # 이상 점수 히트맵
├── 00000_label0_score3.76e-09_s_recon.png    # 복원 오차 히트맵
├── 00000_label0_score3.76e-09_s_feat.png     # 특징 attention 히트맵
├── 00000_label0_score3.76e-09_overlay.png    # 원본 + 히트맵 오버레이 (중요!)
└── ...
```

### 2. 주요 결과 파일

#### `dual_scores.json`

모든 이미지의 이상 점수를 포함합니다:

```json
[
  {
    "idx": 0,
    "label": 0,
    "score": 3.76e-09
  },
  {
    "idx": 1,
    "label": 1,
    "score": 5.96e-08
  },
  ...
]
```

- `idx`: 이미지 인덱스
- `label`: 실제 라벨 (0=정상, 1 이상=이상)
- `score`: 이상 점수 (낮을수록 정상, 높을수록 이상)

#### 이미지 파일

각 이미지마다 6개의 파일이 생성됩니다:

1. **`*_input.png`**: 원본 이미지
2. **`*_recon.png`**: 모델이 재구성한 이미지
3. **`*_score.png`**: 최종 이상 점수 히트맵 (hot 컬러맵)
4. **`*_s_recon.png`**: 복원 오차 히트맵
5. **`*_s_feat.png`**: 특징 attention 히트맵
6. **`*_overlay.png`**: 원본 + 히트맵 오버레이 ⭐ **가장 중요!**

### 3. 히트맵 해석

`*_overlay.png` 파일을 보면:
- **검은색/어두운 색**: 정상 영역
- **어두운 빨간색**: 낮은 이상 가능성 (threshold 미만)
- **빨간색**: 이상 가능성 중간 (threshold 이상)
- **노란색**: 이상 가능성 높음
- **흰색**: 이상 가능성 매우 높음

### 4. 성능 평가 (선택사항)

추론 결과를 평가하려면:

```bash
python mvtec_root\chest_xray\main.py \
  --mode evaluate \
  --json_path outs_dual/dual_scores.json \
  --out_dir evaluation_results \
  --model_name DualAnomaly \
  --class_names good pneumonia tuberculosis
```

평가 결과는 `evaluation_results/` 디렉토리에 저장됩니다.

---

## 문제 해결

### 1. 메모리 부족 오류

**문제**: `CUDA out of memory` 또는 메모리 부족

**해결**:
- `--test_limit_per_class` 옵션으로 샘플 수 제한
- `--batch_size`를 줄이기 (기본값은 1이지만 확인)
- CPU 모드로 실행 (GPU 사용 안 함)

### 2. 체크포인트 파일 없음

**문제**: `checkpoints/dual_best.pt` 파일이 없음

**해결**:
- Git에서 체크포인트 파일이 제외되었을 수 있습니다
- 팀 리더에게 체크포인트 파일 요청
- 또는 별도로 체크포인트 파일 다운로드

### 3. 데이터 경로 오류

**문제**: `FileNotFoundError` 또는 경로 오류

**해결**:
- `--data_root` 경로가 올바른지 확인
- `mvtec_root/chest_xray/` 디렉토리 구조 확인
- 상대 경로 대신 절대 경로 사용

### 4. 이미지 변환 오류

**문제**: 변환 중 오류 발생

**해결**:
- `archive/train.csv` 파일이 있는지 확인
- `archive/train/` 디렉토리에 이미지 파일이 있는지 확인
- 경로에 한글이나 특수문자가 없는지 확인

---

## 추가 정보

### 기타 참고 파일 안내

- **`AE_MODEL_LIMITATION.md`**:  
  - Autoencoder/Anomaly 모델의 한계, 개선안, 학습 전략 등 상세 분석  
  - Dual Branch 방식의 설계 및 튜닝 가이드, 실험 결과 해설  
  - 학습 시 발생할 수 있는 주요 이슈, 하이퍼파라미터 조정법, 실제 개선 효과 등 실용적 조언 포함  
  - _세부적인 성능 개선과 학습 심화 내용이 궁금하다면 필독!_
  
- **`HEATMAP_IMPLEMENTATION.md`**:  
  - 이상 점수 히트맵의 생성 방식, 후처리, 시각화 소스 설명  
  - 스코어 맵 계산, 상위 k% 통계 처리, overlay 이미지 등  
  - _결과 해석이나 커스텀 히트맵이 필요할 때 참고_

- **`OUTLIER_HANDLING_IMPROVEMENTS.md`**:  
  - 이상치(outlier) 처리 기법 및 스코어 정규화 방법 설명  
  - Robust score 집계, 상위-percentile 평균, 이상점 noise 완화 등  
  - _모델 스코어의 신뢰성/일관성이 중요할 때 참고_

- **`README.md`**:  
  - 전체 프로젝트 설치, 핵심 실행법, 기본 개요  
  - _프로젝트를 처음 시작한다면 가장 먼저 읽을 문서_

---


