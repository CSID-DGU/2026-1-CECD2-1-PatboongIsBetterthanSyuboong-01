package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.PrescriptionFeedback;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PrescriptionFeedbackRepository extends JpaRepository<PrescriptionFeedback, Integer> {
    List<PrescriptionFeedback> findByHistoryId(int historyId);
    List<PrescriptionFeedback> findByHistoryDiagnoseId(Integer historyDiagnoseId);

    /** accepted/rejected 재저장 시 기존 레코드 삭제 (missed는 보존) */
    @Modifying(clearAutomatically = true)
    @Query("DELETE FROM PrescriptionFeedback f WHERE f.historyId = :historyId AND f.status <> 'missed'")
    void deleteNonMissedByHistoryId(@Param("historyId") int historyId);

    /** missed 재저장 시 기존 레코드 삭제 (accepted/rejected는 보존) */
    @Modifying(clearAutomatically = true)
    @Query("DELETE FROM PrescriptionFeedback f WHERE f.historyId = :historyId AND f.status = 'missed'")
    void deleteMissedByHistoryId(@Param("historyId") int historyId);
}
