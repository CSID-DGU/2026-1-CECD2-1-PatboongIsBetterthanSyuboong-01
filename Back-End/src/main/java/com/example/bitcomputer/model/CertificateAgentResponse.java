package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Python(FastAPI) certificate_api → Spring 응답 본문.
 *
 * <p>Gemini 가 생성한 진단서 소견 문자열이 {@code medicalCertificate} 에 담긴다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class CertificateAgentResponse {

    /** Gemini 가 생성한 진단서 소견 문자열. */
    @JsonProperty("medicalCertificate")
    private String medicalCertificate;
}
