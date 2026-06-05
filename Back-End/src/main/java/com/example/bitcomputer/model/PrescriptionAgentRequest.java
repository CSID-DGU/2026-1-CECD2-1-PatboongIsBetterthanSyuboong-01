package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Spring → Python(FastAPI) prescription_api 요청 본문.
 *
 * <p>Python 측 {@code PrescriptionRecommendRequest} 와 필드명이 1:1 로 매칭된다.
 * ArangoDB 에 저장된 방문·처방 그래프 (visits, order_lines, prescription_masters …) 와
 * 정규화된 feature 를 Python LangChain 에이전트로 넘긴다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class PrescriptionAgentRequest {

    /**
     * Arango {@code visits.내원번호_norm} 또는 {@code visit_id}({@code VISIT_xxx}) 에 매칭되는 문자열.
     * MySQL 의 {@code patient.id} 또는 별도 매핑된 내원번호를 그대로 문자열로 보낸다.
     */
    @JsonProperty("patient_id")
    private String patientId;

    /** 현재 진료의 증상 요약 (문자열 권장). */
    private String symptoms;

    /** 과거 진료·특이사항 요약 (문자열 권장; 길면 여러 줄). */
    private String history;

    /**
     * 현재 방문에 기록된(또는 과거 진료의) 처방 라인 배열.
     * 각 원소는 {@code {내원번호, 처방시퀀스, 처방코드, 처방명}} 형태.
     * 비어 있고 {@link #fetchTopRxFromArango} 가 true 면 Python 이 Arango 에서 채운다.
     */
    @JsonProperty("top_rx")
    private List<Map<String, Object>> topRx;

    /** 유사 환자·처방 결과 요약 (문자열). 데이터가 없으면 빈 문자열로. */
    @JsonProperty("similar_outcomes")
    private String similarOutcomes;

    /**
     * (선택) diagnosis_has_mention / prescription_has_mention / note_mentions 기반 보조 정보.
     * 사용하지 않으면 null.
     */
    @JsonProperty("mention_links")
    private List<Map<String, Object>> mentionLinks;

    /** (선택) 임상의가 자연어로 덧붙인 조건 / 요청. */
    @JsonProperty("clinician_question")
    private String clinicianQuestion;

    /**
     * true 이고 {@link #topRx} 가 비어 있으면 Python 이 {@link #patientId} 로
     * Arango visits → visit_has_order → order_lines 경로를 읽어 top_rx 를 채운다.
     */
    @JsonProperty("fetch_top_rx_from_arango")
    private Boolean fetchTopRxFromArango;

    /** {@link #fetchTopRxFromArango} 가 true 일 때 가져올 최대 행 수. (기본 80) */
    @JsonProperty("arango_top_rx_limit")
    private Integer arangoTopRxLimit;

    /**
     * 상병 코드 목록 (예: E11). 비어 있지 않으면 Python 이 Arango 에서 동일 상병이 연결된 방문들의
     * 처방 빈도 코호트를 조회해 {@code similar_outcomes} 및 {@code top_rx} 후보에 병합한다.
     */
    @JsonProperty("disease_codes")
    private List<String> diseaseCodes;

    /** true 이면 {@link #diseaseCodes} 가 있을 때 코호트 AQL 을 실행한다. */
    @JsonProperty("fetch_cohort_rx_from_arango")
    private Boolean fetchCohortRxFromArango;

    /** 코호트 처방 통계 상위 N 건 (Python 기본 40). */
    @JsonProperty("arango_cohort_rx_limit")
    private Integer arangoCohortRxLimit;

    /** (선택) LLM 모델 ID 를 덮어쓰고 싶을 때. null 이면 Python 기본값 사용. */
    private String model;

    /** (선택) LLM 샘플링 온도. null 이면 Python 기본값 사용. */
    private Double temperature;
}
