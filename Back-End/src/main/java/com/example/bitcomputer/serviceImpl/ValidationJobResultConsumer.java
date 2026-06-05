package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.ValidationJobRepository;
import com.example.bitcomputer.Repository.ValidationResultRepository;
import com.example.bitcomputer.entity.ValidationJob;
import com.example.bitcomputer.entity.ValidationJobStatus;
import com.example.bitcomputer.entity.ValidationResult;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Map;

@Slf4j
@Service
public class ValidationJobResultConsumer {
    private static final ZoneId SEOUL_ZONE = ZoneId.of("Asia/Seoul");

    private final ValidationJobRepository validationJobRepository;
    private final ValidationResultRepository validationResultRepository;
    private final ObjectMapper objectMapper;

    public ValidationJobResultConsumer(
            ValidationJobRepository validationJobRepository,
            ValidationResultRepository validationResultRepository,
            ObjectMapper objectMapper) {
        this.validationJobRepository = validationJobRepository;
        this.validationResultRepository = validationResultRepository;
        this.objectMapper = objectMapper;
    }

    @RabbitListener(queues = "${validation.rabbitmq.result-queue:validation.prescription.result}")
    public void consume(Map<String, Object> message) {
        String jobId = String.valueOf(message.get("jobId"));
        ValidationJob job = validationJobRepository.findByJobId(jobId)
                .orElseThrow(() -> new IllegalStateException("ValidationJob not found: " + jobId));
        String status = String.valueOf(message.getOrDefault("status", ""));
        if ("RUNNING".equals(status)) {
            job.setStatus(ValidationJobStatus.RUNNING);
            job.setStartedAt(LocalDateTime.now(SEOUL_ZONE));
            validationJobRepository.save(job);
            return;
        }
        if ("FAILED".equals(status)) {
            job.setStatus(ValidationJobStatus.FAILED);
            job.setLastError(String.valueOf(message.getOrDefault("error", "validation agent failed")));
            job.setCompletedAt(LocalDateTime.now(SEOUL_ZONE));
            validationJobRepository.save(job);
            return;
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) message.get("result");
        if (result == null) {
            job.setStatus(ValidationJobStatus.FAILED);
            job.setLastError("validation result payload is empty");
            job.setCompletedAt(LocalDateTime.now(SEOUL_ZONE));
            validationJobRepository.save(job);
            return;
        }

        ValidationResult validationResult = new ValidationResult();
        validationResult.setEventId(0L);
        validationResult.setHistoryId(job.getHistoryId());
        validationResult.setOverallStatus(String.valueOf(result.getOrDefault("overallStatus", "NEEDS_REVIEW")));
        validationResult.setSummary(String.valueOf(result.getOrDefault("summary", "")));
        validationResult.setResultJson(toJson(result));
        validationResult.setShouldNotifyDoctor(Boolean.TRUE.equals(result.get("shouldNotifyDoctor")));
        validationResult.setShouldBlockAutoPrescription(Boolean.TRUE.equals(result.get("shouldBlockAutoPrescription")));
        ValidationResult saved = validationResultRepository.save(validationResult);

        job.setStatus(ValidationJobStatus.DONE);
        job.setResultId(saved.getId());
        job.setLastError(null);
        job.setCompletedAt(LocalDateTime.now(SEOUL_ZONE));
        validationJobRepository.save(job);
        log.info("검증 job 결과 저장 완료 - jobId={} resultId={}", jobId, saved.getId());
    }

    private String toJson(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("validation result 직렬화 실패", e);
        }
    }
}
