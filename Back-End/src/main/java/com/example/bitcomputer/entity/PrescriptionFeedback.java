package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "prescription_feedback")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PrescriptionFeedback {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    /** 해당 피드백이 속한 진료 기록 */
    @Column(name = "history_id", nullable = false)
    private int historyId;

    /** AI 추천 세션 식별자 (history_diagnose_id) — nullable */
    @Column(name = "history_diagnose_id")
    private Integer historyDiagnoseId;

    /** 추천 순위 (1, 2, 3) — rank는 MySQL 예약어이므로 rec_rank 사용 */
    @Column(name = "rec_rank", nullable = false)
    private int rank;

    /** diagnose 테이블 PK — DB 미매칭 시 null */
    @Column(name = "prescription_id")
    private Integer prescriptionId;

    @Column(name = "prescription_code", nullable = false)
    private String prescriptionCode;

    @Column(name = "prescription_name", nullable = false)
    private String prescriptionName;

    @Column(name = "confidence_score")
    private Double confidenceScore;

    @Column(name = "reason", columnDefinition = "TEXT")
    private String reason;

    /** 의사의 선택 여부: "accepted" 또는 "rejected" */
    @Column(name = "status", nullable = false)
    private String status;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;
}
