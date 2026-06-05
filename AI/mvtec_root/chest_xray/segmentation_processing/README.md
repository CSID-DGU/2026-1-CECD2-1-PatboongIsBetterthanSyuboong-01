# Segmentation Processing Pipeline

본 디렉터리는 **CheXmask-Database-main** 오픈소스 저장소의 HybridGNet 코드를 기반으로, 흉부 X-ray 이미지에 대한 ROI(폐/심장) 마스킹을 수행하기 위한 래퍼 모듈을 제공합니다.  
참고: <https://github.com/ngaggion/CheXmask-Database> (논문: [CheXmask: a large-scale dataset of anatomical segmentation masks for multi-center chest x-ray images](https://www.nature.com/articles/s41597-024-03358-1))

## 구성 요소

| 파일 | 설명 |
|------|------|
| `hybridgnet_segmenter.py` | CheXmask HybridGNet 모델을 로드하고, 단일 이미지에 대해 ROI 마스크를 생성/적용하는 래퍼 클래스 (`HybridGNetSegmenter`) |
| `roi_mask_pipeline.py` | CheXpert CSV를 읽어 **PA + Frontal** 샘플만 필터링하고, ROI 마스킹 이미지를 생성하여 별도의 `archive_pa` 루트로 저장하는 CLI 파이프라인 |
| `__init__.py` | 패키지 초기화 및 기본 export |

## ROI 마스킹 파이프라인 실행 방법

```powershell
cd C:\Project\AI
python -m mvtec_root.chest_xray.segmentation_processing.roi_mask_pipeline `
    --source_root mvtec_root/chest_xray/archive `
    --target_root mvtec_root/chest_xray/archive_pa `
    --device cuda:0 ` #cuda 미설치 시 cpu로 실행 --device cpu
    --skip-existing
```

### 주요 옵션
- `--source_root`: 원본 CheXpert 구조(`train/`, `valid/`, `*.csv`) 위치.
- `--target_root`: ROI 마스킹 및 PA 필터링 결과가 저장될 위치.
- `--device`: HybridGNet 추론에 사용할 Torch 디바이스 (`cuda:0`, `cpu` 등).
- `--weights`: 필요 시 다른 가중치 경로 지정 (기본값은 CheXmask 제공 `Weights/SegmentationModel/bestMSE.pt`).
- `--skip-existing`: 이미 처리된 이미지는 건너뛰어 재실행을 빠르게 함.
- `--limit`: 디버깅/테스트용으로 일부 샘플만 처리.

실행이 완료되면:
- `target_root` 내부에 `train/`·`valid/` 폴더가 원본과 동일한 상대 경로로 생성됩니다.
- CSV(`train.csv`, `valid.csv`)는 PA/Frontal 샘플만 남도록 재작성됩니다.
- ROI 바깥 영역이 마스킹된 이미지가 저장되며, 이후 학습 스크립트의 기본 경로(`--image_root mvtec_root/chest_xray/archive_pa`)와 연동됩니다.

> ⚠️ GPU 실행 시 PyTorch Geometric 버전을 CheXmask 코드와 호환되도록 맞춰야 합니다. (예: torch-geometric 2.4.0, torch-scatter 2.1.2, torch-sparse 0.6.18, torch-cluster 1.6.0, torch-spline-conv 1.2.2 with CUDA 12.1 wheels).  
> 설치 전에는 `--device cpu`로 먼저 실행하는 것을 권장합니다.

ROI 마스킹이 끝난 뒤 Dual Branch 이상탐지용 MVTec 구조가 필요하다면, 변환 스크립트를 다시 실행하세요.

```powershell
cd C:\Project\AI
python convert_chexpert_to_mvtec.py
```

## 직접 사용 예시 (파이썬)

```python
from pathlib import Path
from mvtec_root.chest_xray.segmentation_processing import HybridGNetSegmenter

segmenter = HybridGNetSegmenter(device="cuda:0")
mask = segmenter.generate_mask(Path("mvtec_root/chest_xray/archive/train/.../image.jpg"))
segmenter.apply_mask(
    Path("mvtec_root/chest_xray/archive/train/.../image.jpg"),
    Path("mvtec_root/chest_xray/archive_pa/train/.../image.jpg"),
)
```

## 주의 사항
1. CheXmask 모델은 입력 이미지를 1024×1024로 리사이즈한 뒤 좌표를 다시 원본 해상도로 되돌리므로, 극단적으로 작은 이미지는 권장하지 않습니다.
2. CheXmask 저장소(`mvtec_root/chest_xray/CheXmask-Database-main`) 및 가중치(`Weights/SegmentationModel/bestMSE.pt`)가 반드시 존재해야 합니다.  
   - 가중치는 CheXmask 논문 저자들이 제공한 공유 링크(예: PhysioNet [https://doi.org/10.13026/6eky-y831](https://doi.org/10.13026/6eky-y831))에서 수동으로 다운로드한 뒤, `CheXmask-Database-main/Weights/SegmentationModel/`에 배치하세요.
3. ROI 마스킹 후 생성되는 이미지들을 기준으로 분류/이상탐지 모델을 학습하면, 환자 외부 영역에서 발생하는 false positive를 구조적으로 줄일 수 있습니다.

## 라이선스 / 출처
- HybridGNet, CheXmask 데이터 및 관련 모델은 원 논문 및 해당 GitHub 저장소 라이선스를 따릅니다.
- 본 디렉터리의 래퍼 코드는 프로젝트 요구사항에 맞게 작성되었으며, CheXmask 오픈소스 프로젝트를 기반으로 합니다.

