package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class GenerateCertificateRequestDTO {
    private Integer historyId;
    private String certificateType; // MILITARY 또는 GENERAL
    private String diagnosisKind;
    private String purpose;
}
