package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Diagnose;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface DiagnoseRepository extends JpaRepository<Diagnose, Integer> {
    Optional<Diagnose> findById(int id);
    Optional<Diagnose> findByCode(String code);
    Optional<Diagnose> findByName(String name);
    Page<Diagnose> findByCodeContainingIgnoreCaseOrNameContainingIgnoreCase(String code, String name, Pageable pageable);
}
