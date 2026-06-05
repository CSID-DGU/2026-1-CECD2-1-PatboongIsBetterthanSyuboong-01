package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class GenerateCertificateResponseDTO {
    private String grantType;
    private String accessToken;
    private String refreshToken;
    private String medicalCertificate;
}
