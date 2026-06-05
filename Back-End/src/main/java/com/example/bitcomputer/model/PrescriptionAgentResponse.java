package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Python(FastAPI) prescription_api → Spring 응답 본문.
 *
 * <p>LLM 이 생성·검증한 처방 3건이 {@code prescriptions} 배열에 담긴다.
 * Python 쪽에서 {@code prescription_agent.parse_prescriptions_llm_response} 로
 * 스키마를 이미 검증하기 때문에, Spring 은 그대로 매핑만 하면 된다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class PrescriptionAgentResponse {

    /** Gemini 가 반환한 rank 1·2·3 처방 항목. 길이는 항상 3 이 보장됨(Python 검증). */
    private List<Item> prescriptions;

    /** Python 이 Arango 로 top_rx 를 보강했으면 true. */
    @JsonProperty("used_arango_top_rx")
    private Boolean usedArangoTopRx;

    /** Arango 에서 로드된 top_rx 행 수. */
    @JsonProperty("arango_top_rx_count")
    private Integer arangoTopRxCount;

    /** 상병 코호트 AQL 로 처방 통계를 병합했으면 true. */
    @JsonProperty("used_cohort_rx")
    private Boolean usedCohortRx;

    /** 코호트에서 가져온 처방 통계 행 수. */
    @JsonProperty("cohort_rx_count")
    private Integer cohortRxCount;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Item {

        /** 1 ~ 3. */
        private int rank;

        /** top_rx 에 등장한 처방명 또는 처방코드 문자열. */
        private String name;

        /** top_rx 의 처방코드. 데이터가 없으면 "미기재". */
        @JsonProperty("prescription_code")
        private String prescriptionCode;

        /** 입력에 용량이 있으면 그대로, 없으면 "미기재". */
        private String dosage;

        /** 데이터 인용 + 짧은 임상/약리 보강(한국어). */
        private String reason;

        /** 모델/후처리 confidence (없으면 null). */
        @JsonProperty("confidence_score")
        private Double confidenceScore;
    }
}
