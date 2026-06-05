package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "radiology_report")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class RadiologyReport {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int radiologyRequestId;
    
    @Column(name = "patient_id", nullable = false)
    private int patientId;
    
    @Column(name = "employee_id", nullable = false)
    private int employeeId;
    
    @Column(name = "dept_id", nullable = false)
    private int deptId;
    
    @Column(name = "symptom_detail", columnDefinition = "TEXT")
    private String symptomDetail;
    
    @Column(name = "memo", columnDefinition = "TEXT")
    private String memo;
    
    @Column(name = "entry_date", nullable = false)
    private LocalDate entryDate;
    
    @Column(name = "detail_image_address", nullable = false)
    private String detailImageAddress;
    
    @Column(name = "result")
    private Boolean result; // true => 의심, false => 이상 없음
    
    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;
    
    @Column(name = "image_url")
    private String imageUrl; // overlay 이미지 경로
    
    @Column(name = "status")
    private String status;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "employee_id", insertable = false, updatable = false)
    private Employee employee;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", insertable = false, updatable = false)
    private Patient patient;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dept_id", insertable = false, updatable = false)
    private Dept dept;
}

