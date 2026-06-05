package com.example.bitcomputer.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CertificateEvaluationResultDTO {

    /** 증상-소견 추론 일치도 점수 (0.0 ~ 1.0) */
    private double score;

    /** 함의(ENTAILMENT) 판정 수 */
    private int entailmentCount;

    /** 전체 (전제, 가설) 쌍 수 */
    private int totalPairs;

    /** NLI 판정에 사용된 전제 문자열 */
    private String premise;

    /** 각 소견 문장별 상세 판정 결과 */
    private List<PairDetail> details;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PairDetail {
        private int index;
        private String hypothesis;
        private String judgment;  // ENTAILMENT | NEUTRAL | CONTRADICTION
        private String reason;
    }
}
