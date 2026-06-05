# X-ray Retrieval Evaluation Report

> 본 보고서는 분류 모델 없이 reconstruction error embedding 의 vector similarity
> 를 통해 disease 후보를 추론하는 시스템에 대한 Leave-One-Out (LOO) 평가 결과입니다.
> **의학적 진단 도구가 아닙니다.**

## 1. 실행 메타

| key | value |
| --- | --- |
| timestamp | 2026-05-07T17:45:57 |
| model_version | ae_squid_v1 |
| embedding_version | mock_pca_v1 |
| embedding_dim | 768 |
| similarity_weights | {"global": 0.5, "right_lung": 0.2, "left_lung": 0.2, "heart": 0.1} |
| view_filter | (all) |

## 2. 데이터 분포

- 등록된 케이스: **205**
- 평가 대상(라벨 있음): **174**
- No Finding/라벨 없음 제외: 31
- top-1 similarity ≥ 0.999 인 query 수: 6 (중복/매우 유사 사례 영향)

### 2.1 disease 분포(등록 기준)

| disease | count |
| --- | ---: |
| lung_opacity | 119 |
| enlarged_cardiomediastinum | 107 |
| support_devices | 100 |
| atelectasis | 75 |
| cardiomegaly | 67 |
| pleural_effusion | 64 |
| edema | 43 |
| consolidation | 32 |
| pneumonia | 8 |
| pneumothorax | 7 |
| lung_lesion | 1 |
| pleural_other | 1 |

### 2.2 view 분포

| view | count |
| --- | ---: |
| AP | 171 |
| PA | 34 |

## 3. Retrieval 메트릭 (multi-label)

- *Relevance* 정의: query 의 disease 집합과 retrieved case 의 disease 집합 교집합 ≠ ∅

- **MRR**: 0.8442
- **mAP**: 0.7516

| k | Hit@k | Precision@k |
| ---: | ---: | ---: |
| 1 | 0.7529 | 0.7529 |
| 3 | 0.9368 | 0.7414 |
| 5 | 0.9655 | 0.7471 |
| 10 | 0.9828 | 0.7425 |
| 20 | 1.0000 | 0.7353 |

## 4. Disease prediction (weighted voting, top-K=20)

- **Top-1 any-match accuracy**: 0.6264
- **Top-3 any-match accuracy**: 0.9540

### 4.1 Per-disease recall

| disease | n | recall@1 | recall@3 |
| --- | ---: | ---: | ---: |
| lung_opacity | 119 | 0.420 | 1.000 |
| enlarged_cardiomediastinum | 107 | 0.336 | 0.963 |
| support_devices | 100 | 0.230 | 0.760 |
| atelectasis | 75 | 0.000 | 0.133 |
| cardiomegaly | 67 | 0.000 | 0.060 |
| pleural_effusion | 64 | 0.000 | 0.062 |
| edema | 43 | 0.000 | 0.023 |
| consolidation | 32 | 0.000 | 0.000 |
| pneumonia | 8 | 0.000 | 0.000 |
| pneumothorax | 7 | 0.000 | 0.000 |
| lung_lesion | 1 | 0.000 | 0.000 |
| pleural_other | 1 | 0.000 | 0.000 |

## 5. ROI severity 분포 (모든 등록 케이스 기준)

| roi | low | medium | high |
| --- | ---: | ---: | ---: |
| full_lung | 19 | 181 | 5 |
| heart | 71 | 133 | 1 |
| left_lung | 21 | 179 | 5 |
| lower_left_lung | 52 | 144 | 9 |
| lower_right_lung | 66 | 131 | 8 |
| mediastinum | 100 | 103 | 2 |
| pleural_region | 23 | 171 | 11 |
| right_lung | 23 | 177 | 5 |
| upper_left_lung | 11 | 188 | 6 |
| upper_right_lung | 7 | 191 | 7 |

## 6. 자동 생성된 finding tag 분포

| finding | count |
| --- | ---: |
| bilateral_diffuse_error | 174 |
| pleural_region_high_error | 11 |
| left_lower_lung_high_error | 9 |
| right_lower_lung_high_error | 8 |
| right_upper_lung_high_error | 7 |
| left_upper_lung_high_error | 6 |
| right_lung_high_error | 5 |
| left_lung_high_error | 5 |
| mediastinum_high_error | 2 |
| cardiac_region_high_error | 1 |

## 7. 한계점 / 해석 가이드

- LOO 평가이며, holdout 셋이 아닙니다. 같은 분포 안에서의 retrieval 능력만 측정합니다.
- ROI mask 가 mock(타원 휴리스틱)이라 의학적 정확도가 떨어집니다. 실제 segmentation 모델로
  교체 시 ROI 통계와 finding tag 신뢰도가 향상될 수 있습니다.
- CheXpert 라벨 자체가 multi-label 이고 분포가 매우 불균형합니다(예: pneumothorax, lung_lesion).
  per-disease 의 n 값이 작은 라벨은 통계적 유의성이 낮습니다.
- top-1 similarity ≥ 0.999 인 케이스는 등록 시 중복 또는 거의 동일한 영상이 있다는 의미이며,
  실제 운영에서는 dedupe 로직이 필요합니다.
- **의학적 진단을 대체하지 않습니다.** 본 결과는 reconstruction error pattern 기반의
  유사 사례 검색 능력을 정량화한 것일 뿐입니다.
