package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class CertificateHistoryDTO {
    private Integer historyId;
    private Integer patientId;
    private String patientName;
    private String patientNumber;   // Patient ID (숫자 → 문자열)
    private Integer age;
    private String gender;
    private String department;
    private String doctor;
    private String issueDate;       // yyyy-MM-dd
    private String symptomDetail;
}
