package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * POST /api/agent/prescription/recommend 응답 (프론트엔드 전송용).
 *
 * <pre>
 * {
 *   "history_diagnose_id": 123,
 *   "recommended_prescriptions": [
 *     { "rank": 1, "prescription_code": "...", "prescription_name": "...",
 *       "reason": "...", "confidence_score": 0.0 },
 *     ...
 *   ]
 * }
 * </pre>
 *
 * <p>grantType / accessToken / refreshToken 은 이 API 에서는 발급하지 않는다.
 */
@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class PrescriptionRecommendResponseDTO {

    @JsonProperty("history_diagnose_id")
    private Integer historyDiagnoseId;

    @JsonProperty("recommended_prescriptions")
    private List<RecommendedPrescriptionItemDTO> recommendedPrescriptions;
}
