package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class CertificateEvaluationRequestDTO {
    private String medicalCertificate;
    private String diseaseCode;
    private String prescriptionCode;
    private String prescriptionName;
}
