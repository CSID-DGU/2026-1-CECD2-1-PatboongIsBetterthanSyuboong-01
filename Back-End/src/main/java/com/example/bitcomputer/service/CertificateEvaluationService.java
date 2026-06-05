package com.example.bitcomputer.service;

import com.example.bitcomputer.model.CertificateEvaluationResultDTO;

public interface CertificateEvaluationService {

    /**
     * 진단서(상병/처방 기반) 증상-소견 추론 일치도 평가
     *
     * @param medicalCertificate AI가 생성한 진단서 전문
     * @param diseaseCode        상병 코드
     * @param prescriptionCode   처방 코드
     * @param prescriptionName   처방명
     * @return                   평가 결과
     */
    CertificateEvaluationResultDTO evaluate(
            String medicalCertificate,
            String diseaseCode,
            String prescriptionCode,
            String prescriptionName
    );
}
