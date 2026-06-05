package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.History;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public interface HistoryRepository extends JpaRepository<History, Integer> {
    @Query("SELECT h FROM History h WHERE h.patientId = :patientId " +
            "AND (:startDate IS NULL OR h.entryDate >= :startDate) " +
            "AND (:endDate IS NULL OR h.entryDate <= :endDate) " +
            "ORDER BY h.entryDate DESC")
    List<History> searchHistories(@Param("patientId") int patientId,
                                  @Param("startDate") LocalDateTime startDate,
                                  @Param("endDate") LocalDateTime endDate);

    @Query("SELECT h FROM History h WHERE h.patientId IN :patientIds " +
            "AND (:startDate IS NULL OR h.entryDate >= :startDate) " +
            "AND (:endDate IS NULL OR h.entryDate <= :endDate) " +
            "ORDER BY h.entryDate DESC")
    List<History> searchHistoriesByPatientIds(@Param("patientIds") List<Integer> patientIds,
                                              @Param("startDate") LocalDateTime startDate,
                                              @Param("endDate") LocalDateTime endDate);

    @Query("SELECT h FROM History h " +
            "WHERE (:startDate IS NULL OR h.entryDate >= :startDate) " +
            "AND (:endDate IS NULL OR h.entryDate <= :endDate) " +
            "ORDER BY h.entryDate DESC")
    List<History> searchAllHistories(@Param("startDate") LocalDateTime startDate,
                                     @Param("endDate") LocalDateTime endDate);
}

