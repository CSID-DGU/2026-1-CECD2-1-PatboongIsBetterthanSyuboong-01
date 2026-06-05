package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Spring → Python(FastAPI) certificate_api 진단서 생성 요청 본문.
 *
 * <p>Python 측 {@code CertificateGenerateRequest} 와 필드명이 1:1 로 매칭된다.
 * MySQL 의 History / HistoryDisease / HistoryDiagnose / Patient 를 읽어 조립한다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class CertificateAgentRequest {

    @JsonProperty("history_id")
    private Integer historyId;

    /** GENERAL 또는 MILITARY */
    @JsonProperty("certificate_type")
    private String certificateType;

    @JsonProperty("patient_name")
    private String patientName;

    @JsonProperty("patient_age")
    private int patientAge;

    @JsonProperty("patient_gender")
    private String patientGender;

    /** yyyy-MM-dd */
    @JsonProperty("entry_date")
    private String entryDate;

    @JsonProperty("symptom_detail")
    private String symptomDetail;

    @JsonProperty("diagnosis_kind")
    private String diagnosisKind;

    private String purpose;

    private List<DiseaseInfo> diseases;

    private List<DiagnoseInfo> diagnoses;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DiseaseInfo {
        private String code;
        private String name;
        private String degree;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DiagnoseInfo {
        private String code;
        private String name;
        private int dose;
        private int time;
        private int days;
    }
}
