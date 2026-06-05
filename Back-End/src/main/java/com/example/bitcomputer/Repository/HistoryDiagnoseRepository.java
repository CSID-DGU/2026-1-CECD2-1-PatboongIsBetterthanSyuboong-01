package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.HistoryDiagnose;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface HistoryDiagnoseRepository extends JpaRepository<HistoryDiagnose, Integer> {
    List<HistoryDiagnose> findByHistoryId(int historyId);
    List<HistoryDiagnose> findByHistoryIdIn(List<Integer> historyIds);
    void deleteByHistoryId(int historyId);
}

