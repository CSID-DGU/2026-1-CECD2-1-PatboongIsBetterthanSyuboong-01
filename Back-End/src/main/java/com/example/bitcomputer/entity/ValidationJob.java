package com.example.bitcomputer.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Data;

import java.time.LocalDateTime;
import java.time.ZoneId;

@Entity
@Table(name = "validation_job")
@Data
public class ValidationJob {
    private static final ZoneId SEOUL_ZONE = ZoneId.of("Asia/Seoul");

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "job_id", nullable = false, unique = true, length = 64)
    private String jobId;

    @Column(name = "history_id", nullable = false)
    private int historyId;

    @Column(name = "patient_id", nullable = false)
    private int patientId;

    @Column(name = "employee_id", nullable = false)
    private int employeeId;

    @Column(name = "dept_id", nullable = false)
    private int deptId;

    @Column(name = "trigger_type", nullable = false, length = 64)
    private String triggerType;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private ValidationJobStatus status = ValidationJobStatus.PENDING;

    @Column(name = "request_payload_json", columnDefinition = "TEXT")
    private String requestPayloadJson;

    @Column(name = "result_id")
    private Long resultId;

    @Column(name = "last_error", columnDefinition = "TEXT")
    private String lastError;

    @Column(name = "retry_count", nullable = false)
    private int retryCount = 0;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        LocalDateTime now = LocalDateTime.now(SEOUL_ZONE);
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now(SEOUL_ZONE);
    }
}
