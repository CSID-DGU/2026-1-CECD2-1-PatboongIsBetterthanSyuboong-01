package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "disease")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Disease {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "code", nullable = false)
    private String code;
    
    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "name_en", nullable = true, columnDefinition = "TEXT")
    private String nameEn;
}
