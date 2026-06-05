package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "medical_certificate")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class MedicalCertificateRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "history_id", nullable = false)
    private Integer historyId;

    @Column(name = "pdf_file_path")
    private String pdfFilePath;

    @Column(name = "agent_used", nullable = false)
    private boolean agentUsed;

    @Column(name = "original_medical_certificate", columnDefinition = "TEXT")
    private String originalMedicalCertificate;

    @Column(name = "saved_medical_certificate", columnDefinition = "TEXT")
    private String savedMedicalCertificate;

    @Column(name = "feedback_type", length = 20)
    private String feedbackType; // APPROVE / MODIFY / REJECT / NONE

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
