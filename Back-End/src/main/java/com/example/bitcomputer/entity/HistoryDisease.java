package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "history_disease")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class HistoryDisease {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "history_id", nullable = false)
    private int historyId;
    
    @Column(name = "degree")
    private String degree;
    
    @Column(name = "code", nullable = false)
    private String code;
    
    @Column(name = "name", nullable = false)
    private String name;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "history_id", insertable = false, updatable = false)
    private History history;
}
