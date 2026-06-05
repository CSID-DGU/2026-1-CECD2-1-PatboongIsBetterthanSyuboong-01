package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.RadiologyReport;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface RadiologyReportRepository extends JpaRepository<RadiologyReport, Integer> {
    Optional<RadiologyReport> findFirstByPatientIdAndStatusOrderByEntryDateDescRadiologyRequestIdDesc(
            int patientId,
            String status);
}

