package com.example.bitcomputer.Repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.example.bitcomputer.entity.Employee;

public interface UserRepository extends JpaRepository<Employee, Integer> {
    Employee findByUsername(String username);
} 