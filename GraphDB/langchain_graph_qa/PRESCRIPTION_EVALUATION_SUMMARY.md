# 처방 추천 에이전트 평가 방식 정리

## 1) 평가 목표

ArangoDB 기반 처방 추천 에이전트의 결과를 정량적으로 검증하기 위해, 처방별 신뢰 점수를 계산하고 `적절/재검토/데이터 부족`으로 분류한다.

핵심 원칙은 다음과 같다.

- 실제 의사 처방 데이터만 사용하더라도, **test 데이터를 기준으로 파라미터를 맞추지 않는다**.
- `train` / `calibration` / `test` 3분할로 데이터 누수를 방지한다.
- 점수 계산 근거(빈도, 유사 환자군)를 명확히 기록한다.

---

## 2) 데이터 분할 프로토콜 (3-way split)

평가 신뢰도를 위해 내원번호(visit) 단위로 데이터를 다음처럼 분리한다.

1. `train`: 에이전트 근거 통계 생성용
2. `calibration`: `w1`, `w2`, threshold 튜닝용
3. `test`: 최종 평가 전용 (튜닝 금지)

### 2-1. 3분할이 필요했던 이유

2분할(train/test)만 쓰면 아래 문제가 발생한다.

- **문제 1: test 정보 역유입(leakage) 위험**
  - test 결과를 보면서 `w1`, `w2`, threshold를 조정하면, 사실상 test를 튜닝 데이터로 사용한 것과 같다.
  - 이 경우 test 성능은 "일반화 성능"이 아니라 "맞춰진 성능"이 된다.

- **문제 2: 과도한 낙관 편향**
  - 의사 실처방 데이터는 모두 positive이기 때문에, 기준선을 잘못 두면 결과가 쉽게 한쪽으로 쏠린다.
  - test를 기준으로 임계값을 만지면 성능이 좋아 보이게 만들기 쉽다.

- **문제 3: 재현성과 설명 가능성 저하**
  - "왜 이 threshold를 썼는가?"에 대해 데이터 기반 근거를 제시하기 어려워진다.
  - 실험을 다시 돌렸을 때 동일 결론을 얻기 어렵다.

### 2-2. 3분할의 장점

- **역할 분리(Role separation)**  
  train은 근거 생성, calibration은 파라미터 확정, test는 검증만 담당하여 목적이 명확하다.

- **신뢰 가능한 최종 성능 추정**  
  test는 파라미터 결정 과정에서 완전히 배제되므로, 보고 성능이 실제 배포 시 성능과 더 가깝다.

- **감사 가능성(Auditability) 향상**  
  어떤 데이터에서 어떤 기준으로 `w1/w2/threshold`를 확정했는지 문서화 가능하다.

- **의료 도메인에서의 설득력 강화**  
  "결과를 좋게 보이게 맞춘 것"이 아니라 "사전 확정된 기준으로 평가한 것"임을 주장할 수 있다.

현재 실행 기준 분할 요약:

- visits: train 749 / calibration 160 / test 161
- rows: train 5991 / calibration 995 / test 1220

관련 스크립트:

- `GraphDB/data_normalize/split_train_calibration_test_csv.py`

---

## 3) 점수 정의

### 3-1. 빈도 기반 점수 `S_freq`

진단 코드 `D`와 처방 약물 `M`의 공동 발생 빈도로 계산한다.

`S_freq(D, M) = Count(D ∩ M) / Count(D)`

복수 진단이 있는 방문의 경우, 해당 약물에 대해 진단별 `S_freq` 중 최대값을 대표값으로 사용한다.

### 3-2. 환자 유사도 기반 점수 `S_similarity`

평가 대상 방문의 진단 코드 집합과 train 방문들의 진단 코드 집합 간 Jaccard 유사도를 계산하고,
그 유사도를 가중치로 약물 사용률을 산출한다.

`S_similarity = sum(sim(v,u) * I(M in u)) / sum(sim(v,u))`

여기서 `sim(v,u)`는 Jaccard 유사도다.

### 3-3. 최종 점수 `Score_total`

`Score_total = w1 * S_freq + w2 * S_similarity`

---

## 4) 파라미터 보정(calibration) 방식

`calibration` 데이터셋에서만 파라미터를 튜닝한다.

- 후보 가중치: `w1 = 0.0 ~ 1.0` (0.1 간격), `w2 = 1 - w1`
- positive: 실제 처방
- pseudo-negative: 해당 방문에 실제로 없는 처방코드 샘플링
- 목표: positive vs pseudo-negative 분리력을 AUC-like 지표로 최대화

Threshold 설정:

- `decision_threshold`: calibration의 positive 점수 분포 분위수(`target_recall` 기반)
- `rare_freq_threshold`: calibration의 positive `S_freq` 하위 5% 분위수

### 4-1. Threshold별 역할

#### (A) `decision_threshold` (최종 판정 경계)

- 역할: `Score_total`을 `적절`과 `재검토 필요`로 나누는 핵심 경계값
- 의미:
  - 값이 높아질수록 `적절` 판정은 줄고 보수적이 된다.
  - 값이 낮아질수록 `적절` 판정은 늘고 민감해진다.
- 현재 방식:
  - calibration의 positive 점수 분포에서 `target_recall`을 만족하는 분위수로 설정
  - 즉, calibration에서 사전에 정한 재현율 목표를 충족하도록 기준을 고정

#### (B) `rare_freq_threshold` (희귀 처방 플래그 경계)

- 역할: 처방의 "희귀성"을 별도 신호로 표시
- 의미:
  - `s_freq < rare_freq_threshold`면 `이례 처방(희귀)` 플래그 부여
  - 이는 최종 판정 자체를 직접 바꾸기보다, 임상의 재확인 우선순위를 높이는 데 사용
- 현재 방식:
  - calibration의 positive `S_freq` 분포 하위 5%를 기준으로 설정
  - 데이터 기반으로 "상대적으로 드문 처방"을 정의

#### (C) `s_freq == 0` and `s_similarity == 0` 규칙 (근거 부재 게이트)

- 역할: 점수 크기와 별개로, 근거 자체가 없는 경우를 분리
- 의미:
  - 이 경우는 `재검토 필요`보다 강하게 `데이터 부족(근거 없음)`으로 분류
  - 낮은 점수의 원인이 "부적절 가능성"인지 "커버리지 부족"인지 구분해준다

### 4-2. 세 threshold/게이트의 관계

- `decision_threshold`: 적절성 판정의 주 경계
- `rare_freq_threshold`: 희귀성 경고 플래그
- `근거 부재 게이트(0/0 규칙)`: 데이터 커버리지 예외 처리

즉, 하나의 임계값으로 모든 것을 해결하지 않고,
`판정` / `경고` / `근거부재`를 분리해서 해석 가능성을 높인다.

---

## 5) 판정 규칙

각 처방 라인에 대해:

- `s_freq == 0` 그리고 `s_similarity == 0`  
  -> `데이터 부족(근거 없음)`
- 위 조건이 아니고 `score_total >= decision_threshold`  
  -> `적절`
- 그 외  
  -> `재검토 필요`

추가 플래그:

- `s_freq < rare_freq_threshold` -> `이례 처방(희귀)`

---

## 6) 최신 실행 결과 (3분할 기준)

실행 파일:

- `GraphDB/langchain_graph_qa/prescription_eval_report_three_way.csv`

자동 보정 결과:

- `w1 = 0.50`
- `w2 = 0.50`
- `rare_freq_threshold = 0.003663`
- `decision_threshold = 0.007367`
- `calibration_auc_like = 0.860209`
- `calibration_rows = 834`

test 최종 평가(1220건):

- `적절`: 954
- `재검토 필요`: 96
- `데이터 부족(근거 없음)`: 170

---

## 7) 재현 방법

### Step 1. 3분할 생성

```bash
python "c:\Project\BitComputerProject\GraphDB\data_normalize\split_train_calibration_test_csv.py" --out-dir "c:\Project\BitComputerProject\GraphDB\data_normalize\three_way_split"
```

### Step 2. calibration 튜닝 + test 최종평가

```bash
python "c:\Project\BitComputerProject\GraphDB\langchain_graph_qa\evaluate_prescription_scores.py" \
  --train-csv "c:\Project\BitComputerProject\GraphDB\data_normalize\three_way_split\train.csv" \
  --calibration-csv "c:\Project\BitComputerProject\GraphDB\data_normalize\three_way_split\calibration.csv" \
  --test-csv "c:\Project\BitComputerProject\GraphDB\data_normalize\three_way_split\test.csv" \
  --auto-calibrate \
  --negatives-per-positive 3 \
  --output-csv "c:\Project\BitComputerProject\GraphDB\langchain_graph_qa\prescription_eval_report_three_way.csv"
```

---

## 8) 결과 해석 시 주의사항

- 이 평가는 "절대적인 임상 정답 여부"보다, **데이터 근거 기반 일관성**을 보는 지표다.
- `데이터 부족(근거 없음)`은 곧바로 부적절을 의미하지 않으며, 근거 데이터 커버리지 이슈일 수 있다.
- threshold를 test에서 다시 조정하면 평가 신뢰도가 떨어지므로 금지한다.
- 운영 단계에서는 분기별/반기별로 calibration 세트를 갱신해 threshold drift를 점검하는 것을 권장한다.

