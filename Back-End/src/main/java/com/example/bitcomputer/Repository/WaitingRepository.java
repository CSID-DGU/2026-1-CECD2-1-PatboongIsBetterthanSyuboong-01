package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Waiting;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface WaitingRepository extends JpaRepository<Waiting, Integer> {
    Optional<Waiting> findByPatientIdAndState(int patientId, String state);
    List<Waiting> findByPatientId(int patientId);
    Optional<Waiting> findFirstByPatientIdOrderByIdDesc(int patientId);
}