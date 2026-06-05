package com.example.bitcomputer.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "patient")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Patient {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "name", nullable = false)
    private String name;
    
    @Column(name = "phone_number", nullable = false)
    private String phoneNumber;
    
    @Column(name = "identity_number", nullable = false, unique = true)
    private String identityNumber;

    @Column(name = "visit_number")
    private String visitNumber;
    
    @Column(name = "birth", nullable = false)
    private LocalDate birth;
    
    @Column(name = "gender", nullable = false)
    private String gender;
}
