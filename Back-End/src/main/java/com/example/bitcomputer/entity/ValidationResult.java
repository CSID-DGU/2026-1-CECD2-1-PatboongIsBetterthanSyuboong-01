package com.example.bitcomputer.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.time.ZoneId;

@Entity
@Table(name = "validation_result")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ValidationResult {
    private static final ZoneId SEOUL_ZONE = ZoneId.of("Asia/Seoul");

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "event_id", nullable = false)
    private Long eventId;

    @Column(name = "history_id", nullable = false)
    private int historyId;

    @Column(name = "overall_status", nullable = false, length = 32)
    private String overallStatus;

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    @Column(name = "result_json", columnDefinition = "TEXT", nullable = false)
    private String resultJson;

    @Column(name = "should_notify_doctor", nullable = false)
    private boolean shouldNotifyDoctor;

    @Column(name = "should_block_auto_prescription", nullable = false)
    private boolean shouldBlockAutoPrescription;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now(SEOUL_ZONE);
    }
}
