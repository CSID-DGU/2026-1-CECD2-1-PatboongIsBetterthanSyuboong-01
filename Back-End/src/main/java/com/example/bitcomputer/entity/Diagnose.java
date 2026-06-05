package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "diagnose")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Diagnose {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "code", nullable = false)
    private String code;
    
    @Column(name = "name", nullable = false, columnDefinition = "TEXT")
    private String name;
    
    @Column(name = "dose", nullable = false)
    private int dose;
    
    @Column(name = "time", nullable = false)
    private int time;
    
    @Column(name = "days", nullable = false)
    private int days;
}
