package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.ValidationJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ValidationJobRepository extends JpaRepository<ValidationJob, Long> {
    Optional<ValidationJob> findByJobId(String jobId);
}
