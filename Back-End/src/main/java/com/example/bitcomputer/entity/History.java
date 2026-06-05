package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "history")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class History {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "employee_id", nullable = false)
    private int employeeId;
    
    @Column(name = "patient_id", nullable = false)
    private int patientId;
    
    @Column(name = "dept_id", nullable = false)
    private int deptId;
    
    @Column(name = "symptom_detail", columnDefinition = "TEXT")
    private String symptomDetail;
    
    @Column(name = "memo", columnDefinition = "TEXT")
    private String memo;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "employee_id", insertable = false, updatable = false)
    private Employee employee;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", insertable = false, updatable = false)
    private Patient patient;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dept_id", insertable = false, updatable = false)
    private Dept dept;

    @Column(name = "entry_date", nullable = false)
    private LocalDateTime entryDate;
}
