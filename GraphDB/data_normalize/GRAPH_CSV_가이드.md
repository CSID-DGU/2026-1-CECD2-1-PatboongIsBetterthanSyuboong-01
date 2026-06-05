# 상병별 처방 데이터 정규화 · Graph CSV 산출물 가이드

## 1. 작업 개요

**목적**: 원본 엑셀(`20260406_상병별 처방코드 추출_특이사항 추가.xlsx`)을 정제한 뒤, 그래프 DB 적재에 쓸 **노드 5종**과 **관계 5종**을 CSV로 내보냅니다.

**구현 위치**: `data_normalize/`  
**실행**: `python3 graph_normalize.py`  
**인코딩**: 모든 출력 CSV는 **UTF-8 with BOM**(`utf-8-sig`)으로 저장하여 Excel에서 한글이 깨지지 않도록 했습니다.

### 처리 파이프라인 (요약)

| 단계 | 내용 |
|------|------|
| Step 2 | 컬럼명을 `상병코드`, `내원번호`, `처방시퀀스`, `처방코드`, `처방명`, `특이사항`으로 고정. 헤더의 공백·숨은 개행 제거 |
| Step 3 | 문자열 정리: `strip`, 줄바꿈 제거, 연속 공백 축소, 빈 문자열은 결측 처리 |
| Step 4 | `*_norm` 컬럼 생성 (코드류는 대문자 통일 등) |
| Step 5 | `visit_id`, `diagnosis_code`, `prescription_code`, `order_line_id`, `note_id`, `duplicate_group_key` 생성 |
| Step 6 | 원본 6컬럼 기준 **완전 중복 행** 제거. 제거 전 전체 행+`is_duplicate_row` 플래그는 `logs/step06_full_row_duplicate_flags.csv`에 저장 |
| Step 7 | 노드별 `groupby` / `drop_duplicates`로 노드 테이블 생성 |
| Step 8 | 관계는 `(시작, 끝)` 쌍의 **distinct**만 추출 |
| Step 9 | 키 null·unique, 엔드포인트 존재, 중복 엣지 검증 |
| Step 10 | `output/`에 CSV 저장 |

### ID·키 규칙 (핵심)

- **`visit_id`**: `VISIT_{내원번호_norm}`
- **`diagnosis_code`**: `상병코드_norm` (진단 노드의 키)
- **`prescription_code`**: `처방코드_norm` (처방 마스터 노드의 키)
- **`order_line_id`**: **구조 키** `visit_id` + `처방시퀀스_norm` + `prescription_code`를 SHA-256(16자)로 요약한 `OL_…`. 동일 방문·동일 시퀀스·동일 처방코드는 **하나의 OrderLine**으로 병합합니다. 같은 키 안에서 **처방명만 다른 경우**는 `raw_name_conflict_flag`·`name_variant_count_within_same_structural_key`로 표시합니다.
- **`note_id`**: `visit_id`와 `특이사항_norm`을 함께 해시한 `NOTE_…` (**방문별** 특이사항). 빈 특이사항은 **ID를 만들지 않음** (`NOTE_NA` 없음).
- **`duplicate_group_key`**: 완전 중복 행 식별용, 6개 norm 전체 해시(`DUP_…`)

---

## 2. 디렉터리 구조

```
data_normalize/
├── input/              # 원본 xlsx (20260406_*.xlsx)
├── output/             # 최종 10개 CSV
├── logs/               # 프로파일링·중복 플래그
├── read_excel.py
├── text_utils.py
├── graph_normalize.py
└── requirements.txt
```

---

## 3. CSV별 설명 (`output/`)

### 노드 (5개)

| 파일 | 설명 | 주요 컬럼 |
|------|------|-----------|
| `01_visit_nodes.csv` | 서로 다른 **내원(방문)** 단위 | `visit_id`, `내원번호_norm` |
| `02_diagnosis_nodes.csv` | **상병코드** 마스터 | `diagnosis_code`, `상병코드_norm` |
| `03_prescription_master_nodes.csv` | **처방코드** 마스터. 코드당 **빈도 최대** 명칭을 `canonical_name`, 서로 다른 명칭 개수를 `name_variant_count`, `name_variant_count > 1`이면 `review_flag` | `prescription_code`, `canonical_name`, `name_variant_count`, `review_flag` |
| `04_order_line_nodes.csv` | **구조 키** 단위 처방 라인(진단·특이사항은 노드에 넣지 않음). `처방명_norm`은 그룹 내 첫 값, 명칭 변형은 플래그로 | `order_line_id`, `visit_id`, `처방시퀀스_norm`, `처방코드_norm`, `prescription_code`, `처방명_norm`, `name_variant_count_within_same_structural_key`, `raw_name_conflict_flag` |
| `05_special_note_nodes.csv` | **방문별** 특이사항(동일 문장이라도 방문이 다르면 다른 `note_id`) | `note_id`, `visit_id`, `특이사항_norm` |

### 관계 (5개)

| 파일 | 관계 의미 | 컬럼 (소스 → 타깃) |
|------|-----------|-------------------|
| `11_rel_visit_has_diagnosis.csv` | 이 방문에 연결된 상병 | `visit_id`, `diagnosis_code` |
| `12_rel_visit_has_order.csv` | 이 방문에 속한 처방 라인 | `visit_id`, `order_line_id` |
| `13_rel_order_refers_to_prescription.csv` | 처방 라인이 참조하는 **처방 마스터**(코드) | `order_line_id`, `prescription_code` |
| `14_rel_visit_has_note.csv` | 방문에 붙은 특이사항(빈 특이사항은 **엣지 없음**) | `visit_id`, `note_id` |
| `15_rel_order_associated_with_diagnosis.csv` | 처방 라인과 함께 기록된 **상병** 연결 | `order_line_id`, `diagnosis_code` |

---

## 4. 로그 파일 (`logs/`)

| 파일 | 내용 |
|------|------|
| `profiling_summary.csv` | 단계별 행 수, 중복 제거 전후, 노드 건수, 검증 결과 요약 |
| `step06_full_row_duplicate_flags.csv` | 중복 제거 **직전** 전체 행 + `is_duplicate_row` (첫 행만 `False`, 나머지 중복은 `True`) |

---

## 5. 결과 정리 (현재 입력 기준)

아래 수치는 `logs/profiling_summary.csv`에 기록된 **한 번의 실행 결과**입니다. 원본 파일이 바뀌면 달라질 수 있습니다.

| 항목 | 값 |
|------|-----|
| 엑셀 로드 행 수 | 8,206 |
| 완전 중복 제거 후 행 수 | 7,711 (제거 495행) |
| `is_duplicate_row == True` | 495 |
| **visit** 노드 수 | 1,070 |
| **diagnosis** 노드 수 | 9 |
| **prescription_master** 노드 수 | 880 |
| **order_line** 노드 수 | 6,809 (구조 키 병합 후; fact 행 7,711 대비 약 902건 축소) |
| **special_note** 노드 수 | 1,025 (방문+텍스트 단위; 빈 특이사항 미포함) |
| **order ↔ diagnosis** 엣지 수 | 7,276 (구조적으로 동일한 라인에 상병이 여러 개 매핑된 경우 다대다로 반영) |
| 검증 | 오류 0건 (`validation_ok` note: `ok`) |

### 해석 참고

- **OrderLine**은 **방문·시퀀스·처방코드**로 식별하므로, 노드 수는 fact 행 수보다 작습니다. 같은 라인에 상병만 다른 행은 하나의 `order_line_id`로 묶이고, `15_rel_order_associated_with_diagnosis`에 상병이 여러 개 붙을 수 있습니다.
- **특이사항**은 방문마다 별도 노드이므로, 과거 “텍스트만으로 묶인” 노드 수(224)보다 **노드·엣지 수가 큽니다**. 빈 특이사항은 노드·`14`번 엣지 모두에서 제외됩니다.
- **visit_nodes 집계 컬럼·diagnosis 코드체계·canonical 고도화** 등은 다음 단계에서 확장 가능합니다.

---

## 6. 재실행 시 유의사항

- 원본 파일은 `input/`에 `20260406_*.xlsx` 패턴으로 **한 파일만** 두는 것을 권장합니다. `read_excel.py`는 `input/`을 우선하고, 없으면 `data_normalize` 루트에서 동일 패턴을 찾습니다.
- 의존성: `pip install -r requirements.txt` (`pandas`, `openpyxl`).
