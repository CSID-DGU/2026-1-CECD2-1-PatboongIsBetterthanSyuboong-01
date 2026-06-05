package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.entity.ValidationEvent;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

@Slf4j
@Component
@ConditionalOnProperty(name = "validation.scheduler.enabled", havingValue = "true", matchIfMissing = true)
public class ValidationEventScheduler {

    private final ValidationOutboxService validationOutboxService;
    private final ValidationEventProcessor validationEventProcessor;

    @Value("${validation.scheduler.batch-size:5}")
    private int batchSize;

    @Value("${validation.scheduler.max-retries:3}")
    private int maxRetries;

    public ValidationEventScheduler(
            ValidationOutboxService validationOutboxService,
            ValidationEventProcessor validationEventProcessor) {
        this.validationOutboxService = validationOutboxService;
        this.validationEventProcessor = validationEventProcessor;
    }

    @Scheduled(
            initialDelayString = "${validation.scheduler.initial-delay-ms:15000}",
            fixedDelayString = "${validation.scheduler.fixed-delay-ms:30000}")
    public void processPendingEvents() {
        List<ValidationEvent> events = validationOutboxService.claimPendingEvents(batchSize);
        if (events.isEmpty()) {
            return;
        }

        for (ValidationEvent event : events) {
            try {
                validationEventProcessor.process(event);
                validationOutboxService.markDone(event);
            } catch (Exception e) {
                log.warn("검증 이벤트 처리 실패 - eventId={} retryCount={} message={}",
                        event.getId(), event.getRetryCount(), e.getMessage(), e);
                validationOutboxService.markFailed(event, e.getMessage(), maxRetries);
            }
        }
    }
}
