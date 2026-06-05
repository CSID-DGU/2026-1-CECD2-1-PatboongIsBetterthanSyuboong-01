package com.example.bitcomputer.model;

import lombok.Data;

import java.util.List;

@Data
public class SavePrescriptionFeedbackRequestDTO {

    private Integer historyId;
    private Integer historyDiagnoseId;
    private List<FeedbackItem> feedbackItems;

    @Data
    public static class FeedbackItem {
        private int rank;
        /** diagnose 테이블 PK (DB 미매칭 시 null) */
        private Integer prescriptionId;
        private String prescriptionCode;
        private String prescriptionName;
        private Double confidenceScore;
        private String reason;
        /** "accepted" or "rejected" */
        private String status;
    }
}
