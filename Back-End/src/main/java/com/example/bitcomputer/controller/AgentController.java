package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.PrescriptionRecommendRequestDTO;
import com.example.bitcomputer.model.SavePrescriptionFeedbackRequestDTO;
import com.example.bitcomputer.model.ValidationJobStartResponseDTO;
import com.example.bitcomputer.service.AgentService;
import jakarta.persistence.EntityNotFoundException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 에이전트(처방 추천 등) API.
 */
@RestController
@RequestMapping("/api/agent/prescription")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    /**
     * {@code history_diagnose_id}에 해당하는 진료의 환자 기준으로 진료 기록을 모은 뒤 처방 후보를 반환한다.
     * 추천 목록·외부 AI 연동은 확장 예정.
     */
    @PostMapping("/recommend")
    public ResponseEntity<ValidationJobStartResponseDTO> recommendPrescription(
            @RequestBody PrescriptionRecommendRequestDTO request) {
        try {
            return ResponseEntity.ok(agentService.recommendPrescription(request));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        } catch (EntityNotFoundException e) {
            return ResponseEntity.notFound().build();
        }
    }

    @PostMapping("/feedback")
    public ResponseEntity<Void> savePrescriptionFeedback(
            @RequestBody SavePrescriptionFeedbackRequestDTO request) {
        try {
            agentService.savePrescriptionFeedback(request);
            return ResponseEntity.ok().build();
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
}
