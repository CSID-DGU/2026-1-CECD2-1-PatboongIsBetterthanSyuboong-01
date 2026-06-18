# Anomaly Detection Model 기반 XAI Agent 시스템

의료 영상 판독 결과를 처방으로 연결하는 명확한 기준이 부재하고, AI 추천에 대한 설명 가능성(Explainability)이 요구되는 문제를 해결하기 위해 개발된 시스템입니다.

X-ray 이상 탐지 → 진단코드-처방 그래프 분석 → LLM 기반 처방 추천 → 검증 및 재추천까지 **End-to-End XAI 파이프라인**을 구현했습니다.


<br>


## 🎬 시연 영상 (Demo)

https://github.com/user-attachments/assets/4304a660-d5e7-4581-ba09-acd90f1ff21b

<br>

## 주요 기능 (Features)

### 1. X-ray 이상 탐지 파이프라인
- 흉부 X-ray 이미지에서 이상 영역 탐지 및 Heatmap 생성
- ROI 마스킹 → 이미지 임베딩 → 벡터 유사도 검색 → 의심 상병 추론

### 2. XAI 처방 추천
- ArangoDB 그래프 기반 진단코드-처방 co-occurrence 분석
- Frequency Score + Similarity Score 가중 합산으로 신뢰도 점수 산출
- Gemini LLM을 활용한 처방 3순위 추천 + 근거 텍스트 생성

### 3. 처방 검증 & 재추천
- RabbitMQ 비동기 통신 기반 ReAct 추론 루프
- X-ray Result Loader / Disease Validator / PubMed Evidence Loader 툴 활용
- 검증 결과에 따라 PASS / REVIEW 분류 및 자동 재추천

### 4. 진단서 자동 생성
- Gemini 기반 한국어 의학 소견 생성
- 일반 / 군 입대용(MILITARY) 템플릿 지원
- 의료진 직접 편집 후 PDF 출력

### 5. EMR 기능
- 환자 등록 및 진료 이력 관리 (CRUD)
- 대기열 상태 관리 (PENDING / COMPLETED / HELD)
- 질병/진단 코드 엑셀 일괄 업로드
- JWT 기반 인증 및 권한 관리


<br>


## 기술 스택 (Tech Stack)
 
| 구분 | 기술 |
|---|---|
| Frontend | Next.js |
| Backend | Spring Boot |
| AI Agent | FastAPI + Gemini (Google), OpenAI gpt-4o-mini |
| AI Model | PyTorch (Anomaly Detection) |
| DB | MySQL, Redis, ArangoDB (Graph) |
| Message Queue | RabbitMQ |
| 외부 API | Google Gemini API, OpenAI API (gpt-4o-mini), PubMed/NCBI API |


<br>


## 시작하기 (Getting Started)

### 사전 요구사항
- Java 17+, Node.js 20+, Python 3.10+
- MySQL 8.x, Redis, ArangoDB, RabbitMQ
- Google Gemini API Key, OpenAI API Key

### 실행 순서

```bash
# 1. DB 및 인프라 서비스 먼저 기동 (MySQL, Redis, ArangoDB, RabbitMQ)
 
# 2. Backend 실행
cd Back-End
./gradlew bootRun
 
# 3. Frontend 실행
cd Front-End
yarn install && yarn dev
 
# 4. AI 서버 실행 (각 서버 디렉토리)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn xray_api:app --host 0.0.0.0 --port 8000
uvicorn prescription_api:app --host 0.0.0.0 --port 8001
uvicorn validation_api:app --host 0.0.0.0 --port 8002
uvicorn certificate_api:app --host 0.0.0.0 --port 5001
```
