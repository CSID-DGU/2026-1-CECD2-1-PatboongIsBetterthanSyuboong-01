# X-ray Reconstruction Error Graph Reasoning System

분류 모델(softmax classifier)을 사용하지 않고, **anomaly detection 모델의 입력 vs 재구성(reconstruction) 차이로 만든 ROI-aware error embedding**을 ArangoDB에 저장한 뒤, **vector similarity search + graph reasoning**으로 유사 사례 기반 질병 후보를 추론하는 연구/프로토타입 시스템입니다.

검증된 동작:
- **anomaly model**: `AI_BackEnd/squid_exp1_256_mask` 의 SQUID 가중치를 그대로 어댑터(`USE_TORCH_ANOMALY=true`)로 재사용 — `verify_squid.py` 로 단독 검증 가능.
- **ArangoDB**: 3.12+ 환경에서 vector index 생성, 미지원 시 자동 fallback(AQL 코사인 직접 계산).
- **CheXpert v1.0(small)** 데이터셋을 변환·등록하는 일괄 스크립트 포함(`scripts/seed_chexpert.py`). valid frontal 202건 등록 + inference 정확도 정성 확인 완료.

> **의료 안전 고지**  
> 본 시스템은 연구/프로토타입이며, 의학적 확정 진단 도구가 아닙니다. 출력은 항상 "유사 사례 기반의 후보 추론"이며, 최종 판독은 영상의학 전문의가 수행해야 합니다.

---

## 1. 시스템 목표

- 분류 모델 없이 X-ray 질병 후보 추론
- reconstruction error pattern을 ROI별로 임베딩
- ArangoDB에 case 임베딩 + 도메인 그래프(disease/finding/ROI 관계)를 함께 저장
- 새 영상에 대해 vector similarity search로 유사 사례를 찾고, graph traversal로 disease/finding/ROI 관계를 확장하여 설명 가능한 후보를 생성

## 2. 왜 분류 모델이 아닌가

| 분류 모델 | 본 시스템 |
|---|---|
| 소수의 closed-set label만 예측 | 새로운 disease tag, finding tag를 등록만 하면 즉시 후보로 등장 |
| softmax score는 잘 보정되지 않음 | top-k 유사 사례 evidence + uncertainty로 설명 가능 |
| 학습된 disease 외 일반화 약함 | 알려지지 않은 패턴도 "유사 사례가 적음 / uncertainty=high"로 표현 |
| ROI 단위 설명력이 약함 | ROI별 error embedding과 통계로 위치 기반 설명 제공 |

## 3. 전체 워크플로우

```
[Image]
   │ preprocess (gray, resize 256, [0,1])
   ▼
[AnomalyModel.reconstruct]  ──►  [recon]
                                   │
[error_map = |input - recon|]  ◄───┘
   │ ROI mask (mock 또는 실제 segmentation)
   ▼
[ROI-masked error map] ──► (left_lung, right_lung, heart, ...)
   │
   ▼
[EmbeddingModel.embed]  ──►  global / left_lung / right_lung / heart embeddings
                              + ROI 통계(mean/p95/area/cc) + auto finding tags + heatmap
                              │
                              ▼
                ArangoDB: xray_cases(document, vector index) + edges(disease/finding/ROI)
```

추론(inference) 시:

1. 같은 파이프라인으로 query embedding을 만듦
2. global + ROI 임베딩으로 ArangoDB vector search → top-k cases
3. ROI severity에 따라 adaptive weight로 점수 합성
4. disease tag weighted voting → 후보 점수
5. 그래프 traversal로 disease ↔ finding ↔ ROI 관계 evidence 수집
6. uncertainty 평가
7. agent가 evidence 외 내용 없이 설명 텍스트 생성

## 4. 폴더 구조

```
XrayGraphRAG/
  app/
    main.py                FastAPI entrypoint
    config.py              환경변수 + 임계값
    api/
      routes_health.py
      routes_admin.py      /admin/init-db
      routes_cases.py      /cases, /cases/{id}, /cases/search-similar, /cases/{id}/feedback
      routes_inference.py  /infer
      dependencies.py      DI 컨테이너
    db/
      arango_client.py
      schema.py            collection / graph / vector index 초기화 + seed
      queries.py           AQL (vector + fallback + traversal)
      repositories.py      CaseRepository
    domain/
      findings.py          ROI 통계 → finding tag
      scoring.py           weighted voting + adaptive weights
      uncertainty.py       uncertainty 평가
    models/schemas.py      Pydantic 모델
    ml/
      base.py              Protocol (AnomalyModel/ROIMaskModel/EmbeddingModel)
      mock_anomaly_model.py
      mock_roi_model.py
      mock_embedding_model.py
      torch_anomaly_model.py    AI_BackEnd/squid_exp1_256_mask 어댑터
      torch_embedding_model.py
      factory.py
    services/
      preprocessing_service.py
      reconstruction_service.py
      error_map_service.py
      roi_mask_service.py
      embedding_service.py
      heatmap_service.py
      storage_service.py
      similarity_service.py
      reasoning_service.py
      agent_service.py
      case_service.py      orchestrator
    utils/{image_utils,id_utils,time_utils}.py
  tests/
    test_error_map.py
    test_roi_stats.py
    test_scoring.py
    test_uncertainty.py
    test_end_to_end.py
    fakes.py
  storage/{images,recon,heatmaps}/
  Dockerfile
  docker-compose.yml
  pytest.ini
  requirements.txt
  .env.example
  README.md
```

## 5. ArangoDB 스키마

| Collection | Type | 설명 |
|---|---|---|
| `xray_cases` | document | case 임베딩/통계/메타 |
| `diseases` | document | disease 노드 |
| `findings` | document | finding 노드 (자동 생성 가능) |
| `rois` | document | ROI 노드 |
| `model_versions` | document | 모델 버전 메타 (확장 영역) |
| `case_has_disease` | edge | xray_cases → diseases |
| `case_has_finding` | edge | xray_cases → findings |
| `case_has_roi_anomaly` | edge | xray_cases → rois |
| `disease_related_finding` | edge | diseases → findings (도메인 지식) |
| `finding_located_in_roi` | edge | findings → rois (도메인 지식) |

`xray_cases` 문서에는 다음 4개의 vector field가 있습니다.

- `globalErrorEmbedding`
- `leftLungErrorEmbedding`
- `rightLungErrorEmbedding`
- `heartErrorEmbedding`

## 6. Vector Index 생성 방법

`POST /admin/init-db`가 자동으로 처리합니다(아래 6.1). 또는 수동으로 ArangoDB JS:

```js
db.xray_cases.ensureIndex({
  name: "globalErrorEmbedding_cosine",
  type: "vector",
  fields: ["globalErrorEmbedding"],
  params: {
    metric: "cosine",
    dimension: 768,
    nLists: 100,
    defaultNProbe: 20,
    trainingIterations: 25
  },
  storedValues: ["view", "modelVersion", "maskVersion"]
});
```

> ArangoDB **3.12+** 의 vector index가 필요합니다. 미지원 버전이면 `repositories.CaseRepository.vector_search`가 자동으로 **AQL fallback(코사인 직접 계산)** 으로 동작합니다(스펙 §6 fallback 요구 반영). 이 fallback은 정확하지만 O(N)이라 case 수가 많아지면 느려집니다.

### 6.1 자동 초기화

```bash
curl -X POST http://localhost:8000/admin/init-db
```

응답 예:

```json
{
  "status": "initialized",
  "vectorIndex": {"vector_supported": true, "details": [...] },
  "graph": "xray_graph",
  "embeddingDim": 768
}
```

## 7. API 사용법

### 7.1 health
```bash
curl http://localhost:8000/health
```

### 7.2 case 등록
```bash
curl -X POST http://localhost:8000/cases \
  -F "image=@chest.png" \
  -F 'diseaseTags=["pneumonia"]' \
  -F 'findingTags=["right_lower_lung_high_error"]' \
  -F "view=PA"
```
응답: `{"caseId": "case_xxxxxxxx", "status": "created"}`

### 7.3 새 이미지 추론
```bash
curl -X POST http://localhost:8000/infer \
  -F "image=@new_chest.png" \
  -F "topK=20" \
  -F "view=PA"
```
응답:
```json
{
  "queryCase": {
    "heatmapPath": "...",
    "roiStats": { "right_lung": {...}, "left_lung": {...}, ... },
    "autoFindings": ["right_lower_lung_high_error"],
    "view": "PA",
    "modelVersion": "ae_squid_v1",
    "maskVersion": "lung_heart_mask_v1"
  },
  "predictedDiseases": [
    {"disease": "pneumonia", "score": 0.78, "supportCases": 13,
     "reason": "Top-20 유사 사례 중 13개가 'pneumonia' 태그를 보유, 현재 영상은 right_lung 영역의 reconstruction error가 두드러집니다."}
  ],
  "notableFindings": [...],
  "similarCases": [...],
  "uncertainty": {"level": "medium", "reasons": [...]},
  "explanation": {
    "summary": "이 결과는 진단이 아니라 reconstruction error pattern 기반의 유사 사례 검색 결과입니다.",
    "predictedDiseases": [...],
    "notableFindings": [...],
    "similarCaseSummary": [...],
    "graphEvidence": {...},
    "limitations": [...],
    "warning": "이 결과는 의학적 진단이 아닙니다. ..."
  },
  "heatmapPath": "...",
  "warning": "이 결과는 의학적 진단이 아닙니다. ..."
}
```

### 7.4 vector search (수동)
```bash
curl -X POST http://localhost:8000/cases/search-similar \
  -H "Content-Type: application/json" \
  -d '{"embedding": [0.1, 0.2, ...], "view": "PA", "topK": 10}'
```

### 7.5 feedback
```bash
curl -X POST http://localhost:8000/cases/case_xxxxxxxx/feedback \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "rad01", "correctedDiseaseTags": ["pneumonia"], "approved": true}'
```

## 8. 실행 방법

### 8.1 로컬(Python)

```bash
cd XrayGraphRAG
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env

# ArangoDB는 별도로 띄워야 함 (docker로 한 줄)
docker run -d --name arangodb -p 8529:8529 -e ARANGO_ROOT_PASSWORD=password arangodb:3.12

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
curl -X POST http://localhost:8000/admin/init-db
```

### 8.2 docker-compose

```bash
cd XrayGraphRAG
docker compose up -d --build
curl -X POST http://localhost:8000/admin/init-db
```

ArangoDB UI: http://localhost:8529 (root / password)

## 8.3 운영 검증 시나리오 (CheXpert + SQUID)

본 저장소는 같은 모노레포 안 `AI_BackEnd/squid_exp1_256_mask` 의 학습된 SQUID 가중치를 그대로 재사용한다.

### 8.3.1 SQUID 어댑터 단독 검증

```powershell
$env:USE_TORCH_ANOMALY="true"
$env:PYTHONIOENCODING="utf-8"
# 가중치 로드 + threshold/mean/std 인지만 확인
python scripts/verify_squid.py
# 1장으로 reconstruction → error map → ROI stats → heatmap 까지
python scripts/verify_squid.py --image storage/test_inputs/chest_001.png --use-mask
```

### 8.3.2 CheXpert v1.0(small) 등록

CheXpert 데이터셋은 `kagglehub` 으로 받는다. 처음 사용한다면 Kaggle 계정에서 API 토큰을
발급받아 `~/.kaggle/kaggle.json` 으로 저장해두면 된다 (Kaggle 계정 → Account → Create New
API Token).

```powershell
# 0) ArangoDB 띄우기 (vector-index 플래그 ON: docker-compose.yml 에 반영됨)
cd XrayGraphRAG
docker compose up -d arangodb

# 1) 스키마/시드 초기화
$env:ARANGO_PASSWORD="<your_password>"
$env:ARANGO_URL="http://localhost:8529"
$env:PYTHONIOENCODING="utf-8"
python scripts/init_db.py

# 2) CheXpert 데이터셋 다운로드 (kagglehub 사용)
pip install kagglehub
# 2-1) kagglehub 캐시 위치 그대로 사용
python scripts/download_chexpert.py
#  → 안내된 archive 경로를 다음 단계에서 --archive 로 그대로 사용
# 2-2) 또는 원하는 경로로 정리 (Windows: directory junction, POSIX: symlink — 디스크 추가 사용 X)
python scripts/download_chexpert.py --dest D:\data\chexpert
# 2-3) 실제 복사가 필요한 경우 (약 11GB+)
python scripts/download_chexpert.py --dest .\archive --mode copy

# 3) 변환 결과 미리보기 (ArangoDB 호출 없음)
python scripts/seed_chexpert.py --archive D:\data\chexpert --split valid --frontal-only --dry-run --limit 5

# 4) valid 셋 등록 (frontal 만, ~200건)
$env:USE_TORCH_ANOMALY="true"
python scripts/seed_chexpert.py --archive D:\data\chexpert --split valid --frontal-only

# 5) train 일부 등록 (예: 200건, U-Ones 정책)
python scripts/seed_chexpert.py --archive D:\data\chexpert --split train --frontal-only --limit 200 --uncertainty ones

# 6) 1장으로 inference 동작 검증
python scripts/smoke_infer.py `
   --image D:\data\chexpert\valid\patient64541\study1\view1_frontal.jpg `
   --view AP --top-k 10
```

> `download_chexpert.py` 옵션 요약:
> - `--dest <path>`: 사용자가 지정하는 archive 경로. 미지정 시 kagglehub 기본 캐시(`~/.cache/kagglehub/...`) 안의 dataset 루트를 그대로 사용.
> - `--mode {junction,symlink,copy}`: dest 로 가져올 방식. Windows 기본 `junction`, POSIX 기본 `symlink` — 디스크 추가 사용 없이 캐시를 그대로 가리킨다. 캐시 폴더가 사라질 위험이 있다면 `--mode copy` 사용.
> - `--cache-dir <path>`: `KAGGLEHUB_CACHE` 환경변수를 지정해 캐시 자체를 다른 디스크로 보낼 때.
> - `--force`: dest 가 비어있지 않아도 진행 (이름 충돌은 자동 skip).

### 8.3.3 vector index 활성화 확인

ArangoDB 3.12 의 vector index 는 experimental 이라 `arangod --experimental-vector-index` 플래그가 켜져 있어야 한다.
- `docker compose up` 으로 띄우면 자동으로 켜져 있음.
- 외부에서 띄운 컨테이너라면 `command: arangod --experimental-vector-index` 추가 필요.
- 미지원 환경에서도 본 시스템은 fallback(AQL 코사인 직접 계산)으로 동작한다(case 가 많으면 느려짐).

```bash
curl -X POST http://localhost:8000/admin/init-db
# 또는 직접: python scripts/init_db.py
# 응답의 vectorIndex.vector_supported 가 true 인지 확인
```

### 8.3.4 Retrieval 평가 (Leave-One-Out)

등록된 케이스 전체를 대상으로 LOO 방식으로 retrieval / disease prediction 성능을 측정한다.

```powershell
# global embedding 만 사용
python scripts/eval_retrieval.py

# global + ROI 가중합 (권장)
python scripts/eval_retrieval.py --use-roi

# 특정 view 만 평가
python scripts/eval_retrieval.py --view PA --out storage/eval/pa_only
```

각 실행은 `storage/eval/<timestamp>/` (또는 `--out` 경로) 에 `metrics.json` 과
사람이 읽을 수 있는 `report.md` 를 자동 저장한다. 두 모드를 모두 수행한 통합 비교
보고서는 [`docs/EVALUATION.md`](docs/EVALUATION.md) 를 참고한다 (CheXpert valid
frontal 202건 + smoke 3건 = 205건 기준 결과 포함).

핵심 결과 (요약):

| metric | global | global + ROI |
| --- | ---: | ---: |
| Hit@1 | 0.718 | **0.753** |
| Hit@5 | 0.948 | **0.966** |
| MRR | 0.828 | **0.844** |
| mAP | **0.753** | 0.752 |
| Top-1 disease (any-match) | 0.603 | **0.626** |
| Top-3 disease (any-match) | **0.960** | 0.954 |

> Mock embedding(random projection) 으로도 dominant 라벨에서 의미 있는 retrieval
> 성능이 나오지만, minority 라벨은 사실상 회수되지 않습니다. contrastive / supervised
> pretrained encoder 도입 시 가장 큰 개선 여지가 있습니다. 자세한 해석과 한계는
> [`docs/EVALUATION.md`](docs/EVALUATION.md) 참조.

### 8.3.5 단일 이미지 추론 + 설명 검증

이미지 1장에 대해 *어떤 disease 후보가 나오는지* + *왜 그렇게 나왔는지(evidence)* 까지
한 번에 확인하려면 `smoke_infer.py` 를 사용한다. 출력은 다음 7블록으로 구성된다.

1. **Predicted Diseases (top-5)**: `disease`, `score`, `supportCases`, `reason` + agent
   evidence(유사 사례 분포 / 두드러진 ROI / 함께 등장한 finding)
2. **Notable Findings**: 유사 사례에서의 finding 등장 빈도 + 현재 영상에서의 ROI evidence
3. **Query ROI Severity / Stats**: 현재 영상의 ROI 별 mean / p95 / max / area% / severity
4. **Similar Cases (top-K)**: similarity, 등록된 disease/finding tag
5. **Uncertainty**: level + 사유 + agent confidence
6. **Agent Explanation**: summary, limitations, graphEvidence 통계 (graph traversal 결과)
7. **Heatmap path / Warning**: 안전 안내문 + reconstruction-error overlay 이미지 경로

또한 `--ground-truth <archive>` 를 주면 CheXpert csv 에서 같은 이미지의 라벨을 자동
조회하여 prediction 과 비교한다 (match@1 / match@3 / missed).

#### 권장 테스트 시나리오

```powershell
# 0) Windows 콘솔에서 한글 깨짐 방지 (선택)
chcp 65001
$env:PYTHONIOENCODING="utf-8"

# 1) 환경 변수 (실제 SQUID 모델 사용)
$env:USE_TORCH_ANOMALY="true"
$env:ARANGO_PASSWORD="<your_password>"
$env:ARANGO_URL="http://localhost:8529"

# 2) 등록된 케이스 1장으로 자가 검증 (sim=1.0 self-match가 보임 = 등록 정상)
python scripts/smoke_infer.py `
   --image D:\data\chexpert\valid\patient64541\study1\view1_frontal.jpg `
   --view AP --top-k 10 `
   --ground-truth D:\data\chexpert

# 3) "등록되지 않은 새 영상" 으로 retrieval 실 동작 검증 (권장)
#    archive 안의 임의 train 이미지로, 미등록 폴더에서 1장 가져와 추론
python scripts/smoke_infer.py `
   --image D:\data\chexpert\train\patient00001\study1\view1_frontal.jpg `
   --view AP --top-k 20 `
   --ground-truth D:\data\chexpert `
   --save storage/eval/infer_p00001.json

# 4) 설명/한계까지 풀 JSON 도 보고 싶을 때
python scripts/smoke_infer.py --image <path> --full --save out.json
```

#### 결과 해석 가이드

- `score` 와 `supportCases` 가 동시에 높을수록 신뢰 가능. 그러나 `Top-1` 과 `Top-2` 의
  score gap 이 작으면 (`uncertainty.reasons` 에 표기) **단정 표현은 피해야 한다**.
- 현재 영상의 ROI 표에서 severity=high 인 영역과 predicted disease 의 임상 관련 ROI 가
  일치하는지 사람이 한 번 더 확인. (예: cardiomegaly → heart, pneumothorax →
  pleural_region 등) 일치하지 않으면 retrieval 신호와 ROI 신호가 어긋난 것이며 false
  positive 가능성이 높다.
- `Similar Cases` 의 disease tag 분포가 query 의 ROI severity 패턴과 다른 경우 — 예를
  들어 query 의 heart 가 high 인데 유사 사례 다수가 lung_opacity 를 가짐 — 이는 mock
  embedding 한계일 가능성이 크다. `eval_retrieval.py` per-disease recall 을 함께 참고.
- `--ground-truth` 가 있는 경우 `match@1 / match@3` 으로 즉시 정량 검증 가능. CheXpert
  valid 에 등록된 케이스로 추론하면 `case_*` 가 sim=1.0 self-match 로 잡히므로 결과가
  과대평가됨. **새 영상**(미등록 train) 으로 검증하는 것을 권장한다.
- `heatmapPath` 이미지를 직접 열어 "ROI severity 표 + 유사 사례의 disease/finding 태그"
  와 **시각적으로 정합** 하는지 확인.

#### FastAPI 로 확인 (대안)

CLI 대신 swagger UI 로 확인할 수도 있다.

```bash
docker compose up -d --build
# 브라우저: http://localhost:8000/docs → POST /infer 에 image 업로드
# 응답 JSON 의 explanation.predictedDiseases[*].evidence 라인이 reason 의 근거
```

## 9. mock 모델과 실제 모델 교체

기본 동작은 결정론적 mock 3종:

- `MockAnomalyModel` : box-blur를 reconstruction으로 사용
- `MockROIModel` : 단순 타원 휴리스틱으로 좌/우/상/하 폐, 심장, pleural, mediastinum 마스크 생성
- `MockEmbeddingModel` : 고정 시드 random projection (default 768-d)

실제 모델로 바꾸려면 환경변수만 설정하면 됩니다.

```bash
USE_TORCH_ANOMALY=true     # AI_BackEnd/squid_exp1_256_mask 의 SQUID model 사용
SQUID_MODEL_DIR=...
USE_TORCH_EMBEDDING=true   # 간단한 conv encoder placeholder (placeholder 그대로면 의미 없음)
```

확장 포인트(같은 인터페이스만 지키면 됨):

- `app/ml/base.py` 의 `AnomalyModel / ROIMaskModel / EmbeddingModel` Protocol
- `app/ml/factory.py` 에서 토글에 따라 어떤 어댑터를 만들지 결정

> 임베딩 차원을 바꾸면 반드시 `EMBEDDING_DIM` 환경변수와 vector index를 함께 변경하고, 기존 case 데이터는 다시 임베딩해야 합니다. (다른 차원의 벡터는 ArangoDB vector index에서 거부됨)

## 10. 의료 안전 고지

- 본 시스템은 영상의학 진단을 대체하지 않습니다.
- "확정적 진단 표현"은 출력하지 않으며, agent는 retrieval/graph evidence 외 정보를 만들어내지 않습니다.
- uncertainty가 항상 표시되며, 유사 사례 부족/품질 저하 시 high로 노출됩니다.

## 11. 한계점

- ROI mask가 mock일 때 의학적으로 정확하지 않습니다.
- mock embedding은 학습되지 않았기 때문에 의미적 유사도가 픽셀 패턴 유사도에 가깝습니다.
- vector index는 ArangoDB 3.12+ 의 experimental 기능입니다(미지원 환경에서는 fallback).
- weighted voting은 case 분포 편향에 영향을 받습니다(특정 disease에 과적합 가능).

## 12. 향후 개선 방향

- 실제 흉부 X-ray segmentation 모델로 ROI mask 교체(폐엽 단위까지)
- contrastive 학습된 embedding (예: CXR-BERT, SimCLR-XR) 적용
- ArangoDB filter pushdown(view/modelVersion) 최적화
- agent에 LLM 통합(단, retrieval evidence 외 generation 금지 system prompt)
- ROI별 confidence calibration (Platt scaling 등)
- expert review feedback loop으로 disease ↔ finding 그래프 동적 업데이트
- 평가 스크립트(retrieval mAP@k, top-1/3 accuracy, uncertainty calibration)

## 13. 테스트

```bash
cd XrayGraphRAG
pip install -r requirements.txt
pytest -ra
```

DB 미의존 단위 테스트(`test_error_map`, `test_roi_stats`, `test_scoring`, `test_uncertainty`)와 in-memory fake repo 기반 통합 테스트(`test_end_to_end`)가 포함됩니다. 실제 ArangoDB 통합 테스트는 docker-compose 환경에서 별도로 수행하세요.

## 14. 평가 지표 설계 (참고)

평가 스크립트는 이 저장소에 포함되어 있지 않지만, 다음 지표를 산출하도록 설계할 수 있습니다.

- Retrieval: top-k disease hit rate, precision@k, recall@k, MRR, mAP
- Disease ranking: top-1 / top-3 accuracy, macro F1, per-disease recall
- Explanation: ROI localization consistency(IoU), finding tag agreement, expert score
- Safety: uncertainty calibration (ECE), low-similarity rejection rate, artifact detection rate
