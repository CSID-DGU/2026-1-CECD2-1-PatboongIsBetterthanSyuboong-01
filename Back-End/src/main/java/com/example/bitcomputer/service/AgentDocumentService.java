package com.example.bitcomputer.service;

import com.example.bitcomputer.model.CertificateFormDTO;
import com.example.bitcomputer.model.CertificateHistoryDTO;
import com.example.bitcomputer.model.GenerateCertificateResponseDTO;
import com.example.bitcomputer.model.PastPrescriptionDTO;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface AgentDocumentService {

    /**
     * 진단서 목록 조회 - 환자명/날짜 범위로 진료 기록 검색
     */
    List<CertificateHistoryDTO> searchCertificates(
            String patientName,
            String patientNumber,
            String department,
            String doctorName,
            String startDate,
            String endDate
    );

    /**
     * 진단서 작성 폼용 환자 상세 조회
     */
    CertificateFormDTO getHistoryDetail(Integer historyId);

    /**
     * 해당 환자의 과거 처방 목록 조회 (현재 historyId 제외)
     */
    List<PastPrescriptionDTO> getPastPrescriptions(Integer historyId);

    /**
     * AI 에이전트를 통한 진단서 내용 생성
     */
    GenerateCertificateResponseDTO generateCertificate(
            Integer historyId,
            String certificateType,
            String diagnosisKind,
            String purpose,
            String username
    );

    /**
     * 프론트 성능검사용(엑셀 행 기반) 진단서 내용 생성
     */
    GenerateCertificateResponseDTO generateTestCertificate(
            String diseaseCode,
            String prescriptionCode,
            String prescriptionName,
            String certificateType,
            String diagnosisKind,
            String purpose,
            String username
    );

    /**
     * 진단서 저장 (PDF 파일 + 메타데이터)
     */
    void saveCertificate(
            Integer historyId,
            MultipartFile pdfFile,
            boolean agentUsed,
            String originalMedicalCertificate,
            String savedMedicalCertificate,
            String feedbackType
    );
}
