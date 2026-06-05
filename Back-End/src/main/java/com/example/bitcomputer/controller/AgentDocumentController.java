package com.example.bitcomputer.controller;

import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.model.CertificateFormDTO;
import com.example.bitcomputer.model.CertificateHistoryDTO;
import com.example.bitcomputer.model.GenerateCertificateRequestDTO;
import com.example.bitcomputer.model.GenerateCertificateResponseDTO;
import com.example.bitcomputer.model.GenerateTestCertificateRequestDTO;
import com.example.bitcomputer.model.PastPrescriptionDTO;
import com.example.bitcomputer.service.AgentDocumentService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/agent/document")
public class AgentDocumentController {

    private final AgentDocumentService agentDocumentService;
    private final JwtTokenProvider jwtTokenProvider;

    public AgentDocumentController(AgentDocumentService agentDocumentService,
                                   JwtTokenProvider jwtTokenProvider) {
        this.agentDocumentService = agentDocumentService;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    /**
     * 진단서 작성 폼용 환자 상세 조회
     * GET /api/agent/document/{historyId}
     */
    @GetMapping("/{historyId}")
    public ResponseEntity<CertificateFormDTO> getHistoryDetail(@PathVariable Integer historyId) {
        try {
            return ResponseEntity.ok(agentDocumentService.getHistoryDetail(historyId));
        } catch (jakarta.persistence.EntityNotFoundException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        } catch (Exception e) {
            log.error("환자 상세 조회 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * 과거처방 조회 (현재 historyId 제외한 해당 환자의 과거 진료 처방)
     * GET /api/agent/document/{historyId}/past-prescriptions
     */
    @GetMapping("/{historyId}/past-prescriptions")
    public ResponseEntity<List<PastPrescriptionDTO>> getPastPrescriptions(@PathVariable Integer historyId) {
        try {
            return ResponseEntity.ok(agentDocumentService.getPastPrescriptions(historyId));
        } catch (jakarta.persistence.EntityNotFoundException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        } catch (Exception e) {
            log.error("과거처방 조회 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * 진단서 목록 조회
     * GET /api/agent/document/search
     *   ?patientName=  &patientNumber=  &department=  &doctorName=
     *   &startDate=yyyy-MM-dd  &endDate=yyyy-MM-dd
     */
    @GetMapping("/search")
    public ResponseEntity<List<CertificateHistoryDTO>> searchCertificates(
            @RequestParam(value = "patientName",   required = false) String patientName,
            @RequestParam(value = "patientNumber", required = false) String patientNumber,
            @RequestParam(value = "department",    required = false) String department,
            @RequestParam(value = "doctorName",    required = false) String doctorName,
            @RequestParam(value = "startDate",     required = false) String startDate,
            @RequestParam(value = "endDate",       required = false) String endDate) {
        try {
            List<CertificateHistoryDTO> result = agentDocumentService.searchCertificates(
                    patientName, patientNumber, department, doctorName, startDate, endDate);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("진단서 목록 조회 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * AI 에이전트 진단서 기재 (병무용 / 일반)
     * POST /api/agent/document/generate
     */
    @PostMapping("/generate")
    public ResponseEntity<?> generateCertificate(
            @RequestBody GenerateCertificateRequestDTO request,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            String username = extractUsername(authHeader);
            if (username == null) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(Map.of("error", "인증 정보가 없습니다."));
            }

            GenerateCertificateResponseDTO response =
                    agentDocumentService.generateCertificate(
                            request.getHistoryId(),
                            request.getCertificateType(),
                            request.getDiagnosisKind(),
                            request.getPurpose(),
                            username);

            return ResponseEntity.ok(response);
        } catch (jakarta.persistence.EntityNotFoundException e) {
            log.warn("진단서 생성 - 대상 없음: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        } catch (Exception e) {
            log.error("진단서 생성 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "진단서 생성 중 오류가 발생했습니다."));
        }
    }

    /**
     * AI 에이전트 진단서 기재 (엑셀 행 기반 테스트용)
     * POST /api/agent/document/generate-test
     */
    @PostMapping("/generate-test")
    public ResponseEntity<?> generateCertificateTest(
            @RequestBody GenerateTestCertificateRequestDTO request,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            String username = extractUsername(authHeader);
            if (username == null) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(Map.of("error", "인증 정보가 없습니다."));
            }

            GenerateCertificateResponseDTO response = agentDocumentService.generateTestCertificate(
                    request.getDiseaseCode(),
                    request.getPrescriptionCode(),
                    request.getPrescriptionName(),
                    request.getCertificateType(),
                    request.getDiagnosisKind(),
                    request.getPurpose(),
                    username
            );
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", e.getMessage()));
        } catch (Exception e) {
            log.error("진단서 테스트 생성 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "진단서 테스트 생성 중 오류가 발생했습니다."));
        }
    }

    /**
     * 진단서 저장
     * POST /api/agent/document/save  (multipart/form-data)
     */
    @PostMapping(value = "/save", consumes = "multipart/form-data")
    public ResponseEntity<?> saveCertificate(
            @RequestParam("historyId") Integer historyId,
            @RequestParam(value = "pdfFile", required = false) MultipartFile pdfFile,
            @RequestParam("agentUsed") boolean agentUsed,
            @RequestParam(value = "originalMedicalCertificate", required = false) String originalMedicalCertificate,
            @RequestParam(value = "savedMedicalCertificate", required = false) String savedMedicalCertificate,
            @RequestParam(value = "feedbackType", required = false, defaultValue = "NONE") String feedbackType,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            String username = extractUsername(authHeader);
            if (username == null) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(Map.of("error", "인증 정보가 없습니다."));
            }

            agentDocumentService.saveCertificate(
                    historyId, pdfFile, agentUsed,
                    originalMedicalCertificate, savedMedicalCertificate, feedbackType);

            // 저장 성공 후 새 토큰 발급
            String accessToken = jwtTokenProvider.generateAccessToken(username);
            String refreshToken = jwtTokenProvider.generateRefreshToken(username);

            return ResponseEntity.ok(Map.of(
                    "grantType", "Bearer",
                    "accessToken", accessToken,
                    "refreshToken", refreshToken
            ));
        } catch (Exception e) {
            log.error("진단서 저장 오류", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "진단서 저장 중 오류가 발생했습니다."));
        }
    }

    private String extractUsername(String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) return null;
        String token = authHeader.substring(7);
        if (!jwtTokenProvider.validateToken(token)) return null;
        return jwtTokenProvider.extractUsername(token);
    }
}
