package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.CertificateEvaluationRequestDTO;
import com.example.bitcomputer.model.CertificateEvaluationResultDTO;
import com.example.bitcomputer.service.CertificateEvaluationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/agent/document")
public class CertificateEvaluationController {

    private final CertificateEvaluationService certificateEvaluationService;

    public CertificateEvaluationController(CertificateEvaluationService certificateEvaluationService) {
        this.certificateEvaluationService = certificateEvaluationService;
    }

    /**
     * 진단서 증상-소견 추론 일치도 평가
     * POST /api/agent/document/evaluate
     */
    @PostMapping("/evaluate")
    public ResponseEntity<?> evaluate(@RequestBody CertificateEvaluationRequestDTO request) {
        if (request.getMedicalCertificate() == null || request.getMedicalCertificate().isBlank()
                || request.getDiseaseCode() == null || request.getDiseaseCode().isBlank()
                || request.getPrescriptionCode() == null || request.getPrescriptionCode().isBlank()
                || request.getPrescriptionName() == null || request.getPrescriptionName().isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "medicalCertificate, diseaseCode, prescriptionCode, prescriptionName은 필수입니다."));
        }

        try {
            CertificateEvaluationResultDTO result = certificateEvaluationService.evaluate(
                    request.getMedicalCertificate(),
                    request.getDiseaseCode(),
                    request.getPrescriptionCode(),
                    request.getPrescriptionName()
            );
            return ResponseEntity.ok(result);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", e.getMessage()));
        } catch (Exception e) {
            log.error("진단서 평가 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "평가 중 오류가 발생했습니다."));
        }
    }
}
