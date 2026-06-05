package com.example.bitcomputer.model;

import lombok.Data;

import java.util.List;

/**
 * Flask AI 서버(/api/ai/document/generate)로 전송되는 진단서 생성 요청 DTO
 */
@Data
public class AgentDocumentGenerateDTO {

    private int historyId;
    private String certificateType;  // MILITARY 또는 GENERAL
    private String patientName;
    private int patientAge;
    private String patientGender;
    private String entryDate;        // yyyy-MM-dd
    private String symptomDetail;
    private List<DiseaseInfo> diseases;
    private List<DiagnoseInfo> diagnoses;

    @Data
    public static class DiseaseInfo {
        private String code;
        private String name;
        private String degree;
    }

    @Data
    public static class DiagnoseInfo {
        private String code;
        private String name;
        private int dose;
        private int time;
        private int days;
    }
}
