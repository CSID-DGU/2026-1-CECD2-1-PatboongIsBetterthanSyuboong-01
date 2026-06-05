package com.example.bitcomputer.model;

import lombok.Data;

import java.util.List;

@Data
public class CertificateFormDTO {

    private Integer historyId;
    private String patientName;
    private String patientNumber;
    private Integer age;
    private String gender;
    private String department;
    private String doctor;
    private String entryDate;       // yyyy-MM-dd
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
        private Integer dose;
        private Integer time;
        private Integer days;
    }
}
