package com.example.bitcomputer.controller;

import com.example.bitcomputer.Repository.ValidationJobRepository;
import com.example.bitcomputer.Repository.ValidationResultRepository;
import com.example.bitcomputer.entity.ValidationJob;
import com.example.bitcomputer.entity.ValidationResult;
import com.example.bitcomputer.model.ValidationJobDTO;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.EntityNotFoundException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/validation-jobs")
public class ValidationJobController {

    private final ValidationJobRepository validationJobRepository;
    private final ValidationResultRepository validationResultRepository;
    private final ObjectMapper objectMapper;

    public ValidationJobController(
            ValidationJobRepository validationJobRepository,
            ValidationResultRepository validationResultRepository,
            ObjectMapper objectMapper) {
        this.validationJobRepository = validationJobRepository;
        this.validationResultRepository = validationResultRepository;
        this.objectMapper = objectMapper;
    }

    @GetMapping("/{jobId}")
    public ResponseEntity<ValidationJobDTO> getJob(@PathVariable String jobId) {
        ValidationJob job = validationJobRepository.findByJobId(jobId)
                .orElseThrow(() -> new EntityNotFoundException("ValidationJob not found: " + jobId));
        ValidationResult result = job.getResultId() == null
                ? null
                : validationResultRepository.findById(job.getResultId()).orElse(null);
        return ResponseEntity.ok(ValidationJobDTO.builder()
                .jobId(job.getJobId())
                .historyId(job.getHistoryId())
                .status(job.getStatus())
                .summary(result != null ? result.getSummary() : null)
                .result(result != null ? parseResult(result.getResultJson()) : null)
                .lastError(job.getLastError())
                .createdAt(job.getCreatedAt())
                .startedAt(job.getStartedAt())
                .completedAt(job.getCompletedAt())
                .build());
    }

    private Map<String, Object> parseResult(String resultJson) {
        if (resultJson == null || resultJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(resultJson, new TypeReference<>() {
            });
        } catch (Exception e) {
            return Map.of("raw", resultJson);
        }
    }
}
