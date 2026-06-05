package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Phrase;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PhraseRepository extends JpaRepository<Phrase, Integer> {
    List<Phrase> findByEmployeeIdOrderByCreatedAtDesc(Integer employeeId);
}
