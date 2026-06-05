package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "history_diagnose")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class HistoryDiagnose {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "history_id", nullable = false)
    private int historyId;
    
    @Column(name = "code", nullable = false)
    private String code;
    
    @Column(name = "name", nullable = false)
    private String name;
    
    @Column(name = "dose", nullable = false)
    private int dose;
    
    @Column(name = "time", nullable = false)
    private int time;
    
    @Column(name = "days", nullable = false)
    private int days;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "history_id", insertable = false, updatable = false)
    private History history;
}
