# 이상 탐지 모델 훈련/추론/평가 명령어 가이드

이 문서는 변경된 파이프라인에 맞춘 PowerShell 명령어를 제공합니다.

## 디렉토리 구조

```
mvtec_root/
  chest_xray/
    train/
      good/              # 정상 학습 데이터
    test/
      good/              # 정상 테스트 데이터
      pneumonia/         # 이상 테스트 데이터 (예시)
      tuberculosis/      # 이상 테스트 데이터 (예시)
    ...
```

## 기본 설정

```powershell
# 프로젝트 루트로 이동
cd C:\Project\AI

# 데이터 루트 경로 설정 (변수 사용 시)
$DATA_ROOT = "mvtec_root\chest_xray"
$CHECKPOINT_DIR = "checkpoints\chest_xray"
$OUTPUT_DIR = "outs"
$EVAL_DIR = "evaluation_results"

# ⚠️ 중요: PowerShell에서 변수 사용 시 주의사항
# 1. 백틱(`) 줄 연속 시 변수 확장 문제가 발생할 수 있음
# 2. 해결 방법:
#    - 방법 A: 한 줄로 작성 (가장 안정적)
#    - 방법 B: 직접 경로 입력 (변수 대신)
#    - 방법 C: 변수 확인 후 사용: Write-Host "DATA_ROOT: $DATA_ROOT"
```

### PowerShell 변수 사용 문제 해결

**문제**: `main.py: error: argument --data_root: expected one argument`

**원인**: PowerShell에서 백틱(`) 줄 연속 시 변수 확장이 제대로 되지 않을 수 있습니다.

**해결 방법**:

```powershell
# ✅ 방법 1: 한 줄로 작성 (가장 안정적, 권장)
python -m mvtec_root.chest_xray.anomaly.main --mode train_dual --data_root "mvtec_root\chest_xray" --img_size 256 --batch_size 16 --epochs 50 --lr 1e-3 --checkpoint_dir "checkpoints\chest_xray" --aug --clahe --noise_sigma 0.01 --consistency_weight 0.1 --stability_weight 0.0 --seed 42

# ✅ 방법 2: 직접 경로 입력 (변수 사용 안 함)
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --data_root "mvtec_root\chest_xray" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "checkpoints\chest_xray" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42

# ✅ 방법 3: 변수 확인 후 사용
$DATA_ROOT = "mvtec_root\chest_xray"
$CHECKPOINT_DIR = "checkpoints\chest_xray"
Write-Host "DATA_ROOT: $DATA_ROOT"  # 변수 확인
Write-Host "CHECKPOINT_DIR: $CHECKPOINT_DIR"  # 변수 확인
# 그 다음 한 줄로 실행
python -m mvtec_root.chest_xray.anomaly.main --mode train_dual --data_root "$DATA_ROOT" --img_size 256 --batch_size 16 --epochs 50 --lr 1e-3 --checkpoint_dir "$CHECKPOINT_DIR" --aug --clahe --noise_sigma 0.01 --consistency_weight 0.1 --stability_weight 0.0 --seed 42
```

---

### 체크포인트 확인 방법

```powershell
# 체크포인트 파일 확인
Get-ChildItem -Path "checkpoints" -Recurse -Filter "*.pt"

# 체크포인트의 latent_ch 확인 (Python)
python -c "import torch; ckpt = torch.load('checkpoints/chest_xray/ae_best.pt', map_location='cpu', weights_only=False); print('latent_ch:', ckpt.get('args', {}).get('latent_ch', 'N/A'))"
```

---

## 1. Autoencoder (AE) 학습

### 기본 학습 (권장)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_autoencoder `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --seed 42
```

### 주요 옵션 설명

- `--aug`: 약한 증강 사용 (Flip/Rotate만)
- `--clahe`: CLAHE 대비 보정 사용
- `--noise_sigma 0.01`: 가우시안 노이즈 표준편차
- `--epochs 50`: 학습 에포크 수
- `--batch_size 16`: 배치 크기

### 변경사항

- ✅ `target_score` 제거: 복원 오차만 최소화
- ✅ `stability_penalty` 제거
- ✅ `latent_ch=256` (기본값, 이미지 해상도 256x256에 맞춤)
- ✅ Dropout 추가: `Dropout2d(p=0.1)`

---

## 2. Dual Branch 학습

### 기본 학습 (권장)

```powershell
# 방법 1: 한 줄로 실행 (가장 안정적, 권장)
python -m mvtec_root.chest_xray.anomaly.main --mode train_dual --data_root "mvtec_root\chest_xray" --img_size 256 --batch_size 16 --epochs 50 --lr 1e-3 --checkpoint_dir "checkpoints\chest_xray" --aug --clahe --noise_sigma 0.01 --consistency_weight 0.1 --stability_weight 0.0 --seed 42

# 방법 2: 변수 사용 + 한 줄로 실행
$DATA_ROOT = "mvtec_root\chest_xray"
$CHECKPOINT_DIR = "checkpoints\chest_xray"
python -m mvtec_root.chest_xray.anomaly.main --mode train_dual --data_root "$DATA_ROOT" --img_size 256 --batch_size 16 --epochs 50 --lr 1e-3 --checkpoint_dir "$CHECKPOINT_DIR" --aug --clahe --noise_sigma 0.01 --consistency_weight 0.1 --stability_weight 0.0 --seed 42

# 방법 3: 백틱(`) 사용 + 직접 경로 입력 (변수 사용 안 함, 가장 확실)
# ⚠️ 주의: 변수($DATA_ROOT) 사용 시 확장 문제가 발생할 수 있으므로 직접 경로 입력 권장
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --data_root "mvtec_root\chest_xray" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "checkpoints\chest_xray" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

### Margin 및 Pseudo Anomaly Ratio 조정

```powershell
# Margin과 Pseudo Anomaly Ratio를 조정하려면
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --margin 0.1 `
    --pseudo_anomaly_ratio 0.3 `
    --seed 42
```

### Margin-based 손실 옵션 (선택)

```powershell
# Margin 값 조정 (기본값: 0.1)
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

> **참고**: `margin`과 `pseudo_anomaly_ratio`는 코드 내부에서 기본값 사용 (각각 0.1, 0.3)

### 주요 옵션 설명

- `--consistency_weight 0.1`: s_recon과 s_feat 일관성 손실 가중치
- `--stability_weight 0.0`: 안정화 패널티 비활성화 (권장)
- `--freeze_ae`: AE 가중치 고정 (선택적)

### 변경사항

- ✅ `target_score` 제거: margin-based 손실 사용
- ✅ Pseudo anomaly 자동 생성 (CutPaste/RandomErasing/Blur)
- ✅ Margin-based 손실: `loss_score = F.relu(margin + pos - neg)`
- ✅ `consistency_weight=0.1`, `stability_weight=0.0` (기본값)
- ✅ `latent_ch=256` (기본값, 이미지 해상도 256x256에 맞춤)

---

## 3. Validation 추론 (Threshold 계산용)

### Validation-normal 데이터로 추론

```powershell
# Dual 모델로 validation 추론
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\dual_best.pt" `
    --out_dir "$OUTPUT_DIR\validation" `
    --clahe
```

### Validation 통계 계산

추론 후 `$OUTPUT_DIR\validation\raw_score_stats.json`에서 통계 확인:

```powershell
# JSON 파일 확인
Get-Content "$OUTPUT_DIR\validation\raw_score_stats.json" | ConvertFrom-Json
```

**Threshold 계산 방법:**
- `threshold = max(p99.5, mean + 3*std)`
- 또는 `threshold = p99.5` (더 보수적)

---

## 4. Autoencoder 추론

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_autoencoder `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\ae_best.pt" `
    --out_dir "$OUTPUT_DIR\ae" `
    --clahe
```

### 출력 파일

- `ae_scores.json`: 이미지별 스코어
- `*_input.png`: 원본 이미지
- `*_recon.png`: 복원 이미지
- `*_err.png`: 오차 히트맵
- `*_overlay.png`: 오버레이 이미지

---

## 5. Dual Branch 추론

### 기본 추론

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\dual_best.pt" `
    --out_dir "$OUTPUT_DIR\dual" `
    --clahe
```

### Validation 통계 사용 (권장)

```powershell
# 방법 1: 한 줄로 작성 (가장 안정적)
python -m mvtec_root.chest_xray.anomaly.main --mode infer_dual --data_root "mvtec_root\chest_xray" --img_size 256 --checkpoint "checkpoints\chest_xray\dual_best.pt" --out_dir "outs\dual" --clahe --val_stats_path "checkpoints\chest_xray\val_normal_stats.json" --eval_json_path "evaluation_results\evaluation_results.json"

# 방법 2: 백틱(`` ` ``) 사용 (백슬래시가 아님!)
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "mvtec_root\chest_xray" `
    --img_size 256 `
    --checkpoint "checkpoints\chest_xray\dual_best.pt" `
    --out_dir "outs\dual" `
    --clahe `
    --val_stats_path "checkpoints\chest_xray\val_normal_stats.json" `
    --eval_json_path "evaluation_results\evaluation_results.json"

# 방법 3: 변수 사용
$DATA_ROOT = "mvtec_root\chest_xray"
$CHECKPOINT_DIR = "checkpoints\chest_xray"  
$OUTPUT_DIR = "outs"
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\dual_best.pt" `
    --out_dir "$OUTPUT_DIR\dual" `
    --clahe `
    --val_stats_path "$CHECKPOINT_DIR\val_normal_stats.json"
```

> **참고**: 
> - `val_stats_path`가 없으면 raw score 사용
> - `eval_json_path`는 선택적 (evaluation 모드에서만 사용)
> - ⚠️ **체크포인트 경로 확인**: `Get-ChildItem -Path "checkpoints" -Recurse -Filter "*.pt"`로 실제 위치 확인
> - ⚠️ **latent_ch 주의**: 추론 시 체크포인트의 `latent_ch`를 따르지 않고 항상 256을 사용합니다

### 출력 파일

- `dual_scores.json`: 이미지별 스코어 (raw + z-score)
- `raw_score_stats.json`: Raw score 통계
- `*_input.png`: 원본 이미지
- `*_recon.png`: 복원 이미지
- `*_score.png`: 스코어 히트맵
- `*_s_recon.png`: 복원 오차 히트맵
- `*_s_feat.png`: 특징 스코어 히트맵
- `*_overlay.png`: 오버레이 이미지

### 변경사항

- ✅ `match_abnormal_to_normal=True` (기본값)
- ✅ Per-image min-max 제거
- ✅ 상위 2% 평균으로 스코어 계산
- ✅ Z-score 표준화 지원 (validation 통계 사용)
- ✅ `latent_ch=256` (기본값, 체크포인트의 `latent_ch`를 따르지 않음)
- ⚠️ **중요**: 체크포인트가 `latent_ch=128`로 학습되었어도 항상 `latent_ch=256`으로 모델을 생성합니다.

---

## 6. 모델 평가

### 통합 평가 (권장: 고정 threshold)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode evaluate `
    --json_path "$OUTPUT_DIR\dual\dual_scores.json" `
    --out_dir "$EVAL_DIR" `
    --model_name "Dual_Branch" `
    --class_names good pneumonia tuberculosis `
    --use_fixed_threshold
```

### F1-max threshold 사용 (비권장)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode evaluate `
    --json_path "$OUTPUT_DIR\dual\dual_scores.json" `
    --out_dir "$EVAL_DIR" `
    --model_name "Dual_Branch" `
    --class_names good pneumonia tuberculosis `
    --use_f1_max_threshold
```

### 평가 결과

- `evaluation_results_*.json`: 전체 평가 결과
- `evaluation_report_*.txt`: 텍스트 리포트
- `roc_curve_*.png`: ROC 곡선
- `pr_curve_*.png`: Precision-Recall 곡선
- `confusion_matrix_*.png`: 혼동 행렬
- `score_distribution_*.png`: 스코어 분포

### 변경사항

- ✅ 고정 threshold 사용 (기본값): validation-normal의 p99.5 또는 mean+3σ
- ✅ 클래스별 샘플 수 균형 확인 로그
- ✅ TN=0 경고 추가

---

## 7. eval_dual_scores.py 사용 (별도 스크립트)

### 고정 threshold 사용 (권장)

```powershell
python eval_dual_scores.py
```

### F1-max threshold 사용

```powershell
python eval_dual_scores.py --f1-max
```

### 출력

- `eval_dual/{timestamp}/eval_*.txt`: 평가 리포트
- `eval_dual/{timestamp}/confusion_matrix_*.png`: 혼동 행렬
- `eval_dual/{timestamp}/pr_curve_*.png`: PR 곡선
- `eval_dual/{timestamp}/roc_curve_*.png`: ROC 곡선
- `eval_dual/{timestamp}/score_distribution_*.png`: 스코어 분포

---

## 전체 파이프라인 실행 예시

### 1단계: AE 학습

```powershell
# ⚠️ 중요: 변수($DATA_ROOT) 사용 시 PowerShell에서 확장 문제가 발생할 수 있습니다.
# 해결: 한 줄로 작성하거나 직접 경로를 입력하세요.

# 방법 1: 한 줄로 작성 (가장 안정적, 권장)
python -m mvtec_root.chest_xray.anomaly.main --mode train_autoencoder --data_root "mvtec_root\chest_xray" --img_size 256 --batch_size 16 --epochs 50 --lr 1e-3 --checkpoint_dir "checkpoints\chest_xray" --aug --clahe --noise_sigma 0.01 --seed 42

# 방법 2: 백틱 사용 + 직접 경로 입력 (변수 사용 안 함)
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_autoencoder `
    --data_root "mvtec_root\chest_xray" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "checkpoints\chest_xray" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --seed 42
```
    --seed 42
```

### 2단계: Dual 학습

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

### 3단계: Validation 추론 (Threshold 계산)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\dual_best.pt" `
    --out_dir "$OUTPUT_DIR\validation" `
    --clahe
```

### 4단계: 테스트 추론

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode infer_dual `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --checkpoint "$CHECKPOINT_DIR\dual_best.pt" `
    --out_dir "$OUTPUT_DIR\dual" `
    --clahe `
    --val_stats_path "$OUTPUT_DIR\validation\raw_score_stats.json"
```

### 5단계: 평가

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode evaluate `
    --json_path "$OUTPUT_DIR\dual\dual_scores.json" `
    --out_dir "$EVAL_DIR" `
    --model_name "Dual_Branch" `
    --class_names good pneumonia tuberculosis `
    --use_fixed_threshold
```

---

## 주요 변경사항 요약

### 학습 단계

1. **AE 학습**
   - `target_score` 제거
   - `stability_penalty` 제거
   - `latent_ch=256` (기본값, 이미지 해상도 256x256에 맞춤)
   - Dropout 추가 (`Dropout2d(p=0.1)`)

2. **Dual 학습**
   - `target_score` 제거
   - Margin-based 손실 사용
   - Pseudo anomaly 자동 생성
   - `consistency_weight=0.1`, `stability_weight=0.0`
   - `latent_ch=256` (기본값)

### 추론 단계

1. **데이터 불균형 해결**
   - `match_abnormal_to_normal=True` (기본값)

2. **스코어 계산**
   - Per-image min-max 제거
   - 상위 2% 평균 사용
   - Z-score 표준화 지원

### 평가 단계

1. **Threshold 계산**
   - 고정 threshold 사용 (기본값)
   - Validation-normal의 p99.5 또는 mean+3σ

2. **로그 개선**
   - 클래스별 샘플 수 균형 확인
   - TN=0 경고

---
**참고**: 
- 체크포인트 경로는 학습 시 `--checkpoint_dir`로 지정한 디렉토리입니다
- 기본값은 `checkpoints\chest_xray\`입니다
- ⚠️ **중요**: 모든 모델은 `latent_ch=256`으로 학습됩니다
- 체크포인트 확인: `Get-ChildItem -Path "checkpoints" -Recurse -Filter "*.pt"`

### 체크포인트 latent_ch 불일치 오류

**오류 메시지**: `RuntimeError: Error(s) in loading state_dict: size mismatch for enc.14.weight`

**원인**: 기존에 `latent_ch=128`로 학습된 체크포인트를 `latent_ch=256` 모델에 로드하려고 시도

**해결 방법**:
1. AE를 `latent_ch=256`으로 새로 학습
2. Dual 학습 시 자동으로 일치하는 체크포인트만 로드됩니다
3. 추론 시에도 항상 `latent_ch=256`을 사용합니다

### GPU 메모리 부족

```powershell
# 배치 크기 감소
--batch_size 8

# 또는 CPU 사용
--device cpu
```

### 학습이 너무 느림

```powershell
# 워커 수 증가
--num_workers 8

# 배치 크기 증가 (메모리 허용 시)
--batch_size 32
```

### 스코어 분산이 너무 작음

- `consistency_weight`를 0.1로 유지
- `stability_weight`를 0.0으로 유지
- Margin 값을 조정 (`--margin` 옵션 사용)
- `latent_ch=256`으로 학습되었는지 확인

### Threshold가 너무 낮음 (TN=0)

- Validation-normal 데이터로 threshold 재계산
- `p99.5` 대신 `mean + 3*std` 사용 고려

---

## 참고사항

1. **데이터 경로**: 모든 경로는 프로젝트 루트(`C:\Project\AI`) 기준
2. **체크포인트**: `checkpoints\chest_xray\`에 저장
3. **출력**: `outs\` 디렉토리에 저장
4. **평가 결과**: `evaluation_results\` 디렉토리에 저장
5. **latent_ch**: 모든 모델은 `latent_ch=256`으로 학습/추론됩니다
6. **기존 체크포인트**: `latent_ch=128`로 학습된 체크포인트는 사용할 수 없습니다

---

## 추가 옵션

### 단계별 학습 (Dual)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --staged_training `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

### Fusion 모듈 사용 (Dual)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --use_fusion `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

### AE 가중치 고정 (Dual 학습 시)

```powershell
python -m mvtec_root.chest_xray.anomaly.main `
    --mode train_dual `
    --freeze_ae `
    --data_root "$DATA_ROOT" `
    --img_size 256 `
    --batch_size 16 `
    --epochs 50 `
    --lr 1e-3 `
    --checkpoint_dir "$CHECKPOINT_DIR" `
    --aug `
    --clahe `
    --noise_sigma 0.01 `
    --consistency_weight 0.1 `
    --stability_weight 0.0 `
    --seed 42
```

