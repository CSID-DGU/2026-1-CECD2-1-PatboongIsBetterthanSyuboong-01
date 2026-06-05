package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.MedicalCertificateRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface MedicalCertificateRepository extends JpaRepository<MedicalCertificateRecord, Integer> {
    Optional<MedicalCertificateRecord> findTopByHistoryIdOrderByCreatedAtDesc(int historyId);
    List<MedicalCertificateRecord> findByHistoryId(int historyId);
    List<MedicalCertificateRecord> findByHistoryIdIn(List<Integer> historyIds);
}
