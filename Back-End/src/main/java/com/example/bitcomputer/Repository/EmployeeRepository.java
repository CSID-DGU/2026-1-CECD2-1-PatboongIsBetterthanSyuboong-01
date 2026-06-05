package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Employee;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface EmployeeRepository extends JpaRepository<Employee, Integer> {
    List<Employee> findAll();
    Optional<Employee> findById(Integer id);
    Employee findByUsername(String username);
    List<Employee> findByNameContainingIgnoreCase(String name);
}
