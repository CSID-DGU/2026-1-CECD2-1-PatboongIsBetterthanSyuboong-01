package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ValidationAgentRequest {
    private Long eventId;
    private String eventType;
    private int historyId;
    private Map<String, Object> eventPayload;
    private Map<String, Object> patientSummary;
    private String symptoms;
    private List<Map<String, Object>> savedDiseases;
    private List<Map<String, Object>> savedPrescriptions;
    private Map<String, Object> xrayInference;
}
