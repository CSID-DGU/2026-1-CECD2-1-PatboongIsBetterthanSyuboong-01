package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.HistoryDisease;
import jakarta.transaction.Transactional;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface HistoryDiseaseRepository extends JpaRepository<HistoryDisease, Integer> {
    List<HistoryDisease> findByHistoryId(int historyId);

    @Transactional
    void deleteByHistoryId(int historyId);
}