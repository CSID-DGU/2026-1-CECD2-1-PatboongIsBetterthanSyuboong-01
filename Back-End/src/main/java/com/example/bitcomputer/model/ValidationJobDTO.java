package com.example.bitcomputer.model;

import com.example.bitcomputer.entity.ValidationJobStatus;
import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ValidationJobDTO {
    private String jobId;
    private int historyId;
    private ValidationJobStatus status;
    private String summary;
    private Map<String, Object> result;
    private String lastError;
    private LocalDateTime createdAt;
    private LocalDateTime startedAt;
    private LocalDateTime completedAt;
}
