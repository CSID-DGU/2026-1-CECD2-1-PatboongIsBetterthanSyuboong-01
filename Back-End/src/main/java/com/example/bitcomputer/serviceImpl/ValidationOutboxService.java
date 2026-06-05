package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.ValidationEventRepository;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.ValidationEvent;
import com.example.bitcomputer.entity.ValidationEventStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.transaction.Transactional;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class ValidationOutboxService {
    private static final ZoneId SEOUL_ZONE = ZoneId.of("Asia/Seoul");

    private final ValidationEventRepository validationEventRepository;
    private final ObjectMapper objectMapper;

    public ValidationOutboxService(
            ValidationEventRepository validationEventRepository,
            ObjectMapper objectMapper) {
        this.validationEventRepository = validationEventRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public ValidationEvent enqueueHistoryValidation(String eventType, History history, Map<String, Object> details) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("eventType", eventType);
        payload.put("historyId", history.getId());
        payload.put("patientId", history.getPatientId());
        payload.put("employeeId", history.getEmployeeId());
        payload.put("deptId", history.getDeptId());
        payload.put("details", details != null ? details : Map.of());

        ValidationEvent event = new ValidationEvent();
        event.setEventType(eventType);
        event.setAggregateType("HISTORY");
        event.setAggregateId(history.getId());
        event.setHistoryId(history.getId());
        event.setStatus(ValidationEventStatus.PENDING);
        event.setPayloadJson(toJson(payload));
        ValidationEvent saved = validationEventRepository.save(event);
        log.info("검증 outbox 이벤트 생성 - eventType={} historyId={}", eventType, history.getId());
        return saved;
    }

    @Transactional
    public List<ValidationEvent> claimPendingEvents(int batchSize) {
        List<ValidationEvent> events = validationEventRepository
                .findTop20ByStatusOrderByCreatedAtAsc(ValidationEventStatus.PENDING)
                .stream()
                .limit(Math.max(1, batchSize))
                .toList();

        for (ValidationEvent event : events) {
            event.setStatus(ValidationEventStatus.PROCESSING);
            event.setLastError(null);
        }
        return validationEventRepository.saveAll(events);
    }

    @Transactional
    public void markDone(ValidationEvent event) {
        event.setStatus(ValidationEventStatus.DONE);
        event.setProcessedAt(LocalDateTime.now(SEOUL_ZONE));
        event.setLastError(null);
        validationEventRepository.save(event);
    }

    @Transactional
    public void markFailed(ValidationEvent event, String errorMessage, int maxRetries) {
        int retryCount = event.getRetryCount() + 1;
        event.setRetryCount(retryCount);
        event.setLastError(trim(errorMessage));
        event.setStatus(retryCount >= maxRetries ? ValidationEventStatus.FAILED : ValidationEventStatus.PENDING);
        validationEventRepository.save(event);
    }

    private String toJson(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("검증 이벤트 payload 직렬화 실패", e);
        }
    }

    private String trim(String value) {
        if (value == null) {
            return null;
        }
        return value.length() > 2000 ? value.substring(0, 2000) : value;
    }
}
