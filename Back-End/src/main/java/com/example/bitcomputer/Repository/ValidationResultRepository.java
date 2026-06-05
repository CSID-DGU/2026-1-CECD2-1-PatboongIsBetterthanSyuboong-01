package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.ValidationResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ValidationResultRepository extends JpaRepository<ValidationResult, Long> {
    List<ValidationResult> findByHistoryIdOrderByCreatedAtDesc(int historyId);
}
