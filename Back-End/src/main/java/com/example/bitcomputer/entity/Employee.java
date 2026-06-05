package com.example.bitcomputer.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "employee")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Employee {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    
    @Column(name = "name", nullable = false)
    private String name;
    
    @Column(name = "dept_id", nullable = false)
    private int deptId;
    
    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false)
    private Role role;
    
    @Column(name = "username", nullable = false, unique = true)
    private String username;
    
    @Column(name = "password", nullable = false)
    private String password;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dept_id", insertable = false, updatable = false)
    @JsonIgnore
    private Dept dept;
}