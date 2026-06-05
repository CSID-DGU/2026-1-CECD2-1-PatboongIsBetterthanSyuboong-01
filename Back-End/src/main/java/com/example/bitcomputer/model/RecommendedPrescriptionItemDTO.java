package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 프론트로 내려가는 처방 추천 1건.
 *
 * <pre>
 * { "rank": 1,
 *   "prescription_code": "string",
 *   "prescription_name": "string",
 *   "reason": "string",
 *   "confidence_score": 0.0 }
 * </pre>
 *
 * Python 응답의 {@code name} → {@code prescription_name},
 * {@code prescription_code} → {@code prescription_code},
 * {@code reason} → {@code reason} 로 매핑된다.
 * {@code confidence_score} 는 현재 Python 스키마에 없어 0.0 기본값으로 채워진다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class RecommendedPrescriptionItemDTO {

    private int id;

    private int rank;

    @JsonProperty("prescription_code")
    private String prescriptionCode;

    @JsonProperty("prescription_name")
    private String prescriptionName;

    private String reason;

    @JsonProperty("confidence_score")
    private double confidenceScore;

    private int dose;

    private int time;

    private int days;
}
