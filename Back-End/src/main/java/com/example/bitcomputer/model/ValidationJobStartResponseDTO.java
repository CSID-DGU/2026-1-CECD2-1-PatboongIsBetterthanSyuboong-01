package com.example.bitcomputer.model;

import com.example.bitcomputer.entity.ValidationJobStatus;
import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ValidationJobStartResponseDTO {
    private String jobId;
    private int historyId;
    private ValidationJobStatus status;
}
