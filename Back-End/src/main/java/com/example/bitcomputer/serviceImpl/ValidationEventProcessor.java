package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryDiagnoseRepository;
import com.example.bitcomputer.Repository.HistoryDiseaseRepository;
import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.PatientRepository;
import com.example.bitcomputer.Repository.RadiologyReportRepository;
import com.example.bitcomputer.Repository.ValidationResultRepository;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.HistoryDiagnose;
import com.example.bitcomputer.entity.HistoryDisease;
import com.example.bitcomputer.entity.Patient;
import com.example.bitcomputer.entity.RadiologyReport;
import com.example.bitcomputer.entity.ValidationEvent;
import com.example.bitcomputer.entity.ValidationResult;
import com.example.bitcomputer.model.ValidationAgentRequest;
import com.example.bitcomputer.model.ValidationAgentResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class ValidationEventProcessor {

    private final HistoryRepository historyRepository;
    private final HistoryDiseaseRepository historyDiseaseRepository;
    private final HistoryDiagnoseRepository historyDiagnoseRepository;
    private final PatientRepository patientRepository;
    private final RadiologyReportRepository radiologyReportRepository;
    private final ValidationResultRepository validationResultRepository;
    private final ValidationAgentClient validationAgentClient;
    private final ObjectMapper objectMapper;

    public ValidationEventProcessor(
            HistoryRepository historyRepository,
            HistoryDiseaseRepository historyDiseaseRepository,
            HistoryDiagnoseRepository historyDiagnoseRepository,
            PatientRepository patientRepository,
            RadiologyReportRepository radiologyReportRepository,
            ValidationResultRepository validationResultRepository,
            ValidationAgentClient validationAgentClient,
            ObjectMapper objectMapper) {
        this.historyRepository = historyRepository;
        this.historyDiseaseRepository = historyDiseaseRepository;
        this.historyDiagnoseRepository = historyDiagnoseRepository;
        this.patientRepository = patientRepository;
        this.radiologyReportRepository = radiologyReportRepository;
        this.validationResultRepository = validationResultRepository;
        this.validationAgentClient = validationAgentClient;
        this.objectMapper = objectMapper;
    }

    public void process(ValidationEvent event) {
        ValidationAgentRequest request = buildRequest(event);
        ValidationAgentResponse response = validationAgentClient.validate(request);
        ValidationResult result = new ValidationResult();
        result.setEventId(event.getId());
        result.setHistoryId(event.getHistoryId());
        result.setOverallStatus(defaultString(response.getOverallStatus(), "NEEDS_REVIEW"));
        result.setSummary(defaultString(response.getSummary(), ""));
        result.setResultJson(toJson(response));
        result.setShouldNotifyDoctor(Boolean.TRUE.equals(response.getShouldNotifyDoctor()));
        result.setShouldBlockAutoPrescription(Boolean.TRUE.equals(response.getShouldBlockAutoPrescription()));
        validationResultRepository.save(result);
    }

    private ValidationAgentRequest buildRequest(ValidationEvent event) {
        History history = historyRepository.findById(event.getHistoryId())
                .orElseThrow(() -> new EntityNotFoundException("History not found: " + event.getHistoryId()));
        Patient patient = patientRepository.findById(history.getPatientId()).orElse(null);

        return ValidationAgentRequest.builder()
                .eventId(event.getId())
                .eventType(event.getEventType())
                .historyId(history.getId())
                .eventPayload(parsePayload(event.getPayloadJson()))
                .patientSummary(toPatientSummary(patient, history))
                .symptoms(history.getSymptomDetail())
                .savedDiseases(toDiseaseRows(historyDiseaseRepository.findByHistoryId(history.getId())))
                .savedPrescriptions(toPrescriptionRows(historyDiagnoseRepository.findByHistoryId(history.getId())))
                .xrayInference(loadLatestXrayInference(history.getPatientId()))
                .build();
    }

    private Map<String, Object> parsePayload(String payloadJson) {
        if (payloadJson == null || payloadJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(payloadJson, new TypeReference<>() {
            });
        } catch (JsonProcessingException e) {
            log.warn("검증 이벤트 payload 파싱 실패 - raw={}", payloadJson, e);
            return Map.of("raw", payloadJson);
        }
    }

    private Map<String, Object> toPatientSummary(Patient patient, History history) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("patientId", history.getPatientId());
        out.put("employeeId", history.getEmployeeId());
        out.put("deptId", history.getDeptId());
        if (patient != null) {
            out.put("name", patient.getName());
            out.put("gender", patient.getGender());
            out.put("birth", patient.getBirth());
            out.put("visitNumber", patient.getVisitNumber());
        }
        return out;
    }

    private List<Map<String, Object>> toDiseaseRows(List<HistoryDisease> diseases) {
        return diseases.stream()
                .map(disease -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", disease.getId());
                    row.put("code", disease.getCode());
                    row.put("name", disease.getName());
                    row.put("degree", disease.getDegree());
                    return row;
                })
                .toList();
    }

    private List<Map<String, Object>> toPrescriptionRows(List<HistoryDiagnose> diagnoses) {
        return diagnoses.stream()
                .map(diagnose -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", diagnose.getId());
                    row.put("code", diagnose.getCode());
                    row.put("name", diagnose.getName());
                    row.put("dose", diagnose.getDose());
                    row.put("time", diagnose.getTime());
                    row.put("days", diagnose.getDays());
                    return row;
                })
                .toList();
    }

    private Map<String, Object> loadLatestXrayInference(int patientId) {
        return radiologyReportRepository
                .findFirstByPatientIdAndStatusOrderByEntryDateDescRadiologyRequestIdDesc(patientId, "completed")
                .map(this::toXrayInference)
                .orElse(null);
    }

    private Map<String, Object> toXrayInference(RadiologyReport report) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("radiologyRequestId", report.getRadiologyRequestId());
        out.put("result", report.getResult());
        out.put("predictedDiseases", parsePredictedDiseases(report.getSummary()));
        out.put("heatmapUrl", report.getImageUrl());
        out.put("status", report.getStatus());
        out.put("entryDate", report.getEntryDate());
        return out;
    }

    private Object parsePredictedDiseases(String summary) {
        if (summary == null || summary.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(summary, Object.class);
        } catch (JsonProcessingException e) {
            return summary;
        }
    }

    private String toJson(ValidationAgentResponse response) {
        try {
            return objectMapper.writeValueAsString(response);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("검증 결과 직렬화 실패", e);
        }
    }

    private String defaultString(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
