package com.example.bitcomputer.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ValidationResultDTO {
    private Long id;
    private Long eventId;
    private int historyId;
    private String overallStatus;
    private String summary;
    private String resultJson;
    private boolean shouldNotifyDoctor;
    private boolean shouldBlockAutoPrescription;
    private LocalDateTime createdAt;
}
