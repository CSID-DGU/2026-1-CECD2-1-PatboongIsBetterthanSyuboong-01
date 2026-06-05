package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class GenerateTestCertificateRequestDTO {
    private String diseaseCode;
    private String prescriptionCode;
    private String prescriptionName;
    private String certificateType;
    private String diagnosisKind;
    private String purpose;
}
