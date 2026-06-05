package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * POST /api/agent/prescription/recommend 요청 본문.
 * {@code history_diagnose_id}로 연결된 진료(history)의 환자 진료 기록을 조회한다.
 */
@Data
public class PrescriptionRecommendRequestDTO {

    @JsonProperty("history_diagnose_id")
    private Integer historyDiagnoseId;

    @JsonProperty("history_id")
    private Integer historyId;

    /**
     * (선택) Arango visits 조회용 환자/내원 식별자.
     * 예: 530524502 또는 VISIT_530524502
     */
    @JsonProperty("arango_patient_id")
    private String arangoPatientId;

    @JsonProperty("use_example_context")
    private Boolean useExampleContext;

    /**
     * (선택) 상병 코드 목록. 비어 있으면 현재 진료에 저장된 {@code HistoryDisease} 코드를 사용한다.
     * Python 측에서 상병별 코호트 처방 빈도(Arango) 조회에 쓰인다.
     */
    @JsonProperty("disease_codes")
    private List<String> diseaseCodes;
}
