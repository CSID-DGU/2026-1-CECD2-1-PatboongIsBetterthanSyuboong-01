package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "waiting")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Waiting {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "patient_id", nullable = false)
    private int patientId;

    @Column(name = "dept_id", nullable = false)
    private int deptId;
    
    @Column(name = "symptom", columnDefinition = "TEXT")
    private String symptom;

    @Column(name = "department")
    private String department;

    @Column(name = "doctor")
    private String doctor;

    @Column(name = "visit_time")
    private String visitTime;

    @Column(name = "visit_type")
    private String visitType;

    @Column(name = "visit_reason", columnDefinition = "TEXT")
    private String visitReason;

    @Column(name = "visit_route")
    private String visitRoute;

    @Column(name = "treatment_type")
    private String treatmentType;

    @Column(name = "memo", columnDefinition = "TEXT")
    private String memo;
    
    @Column(name = "entry_date", nullable = false)
    private LocalDateTime entryDate;
    
    @Column(name = "state", nullable = false)
    private String state;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", insertable = false, updatable = false)
    private Patient patient;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dept_id", insertable = false, updatable = false)
    private Dept dept;
}
