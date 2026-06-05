package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Patient;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PatientRepository extends JpaRepository<Patient, Integer> {
    boolean existsByIdentityNumber(String identityNumber);
    Patient findByIdentityNumber(String identityNumber);
    List<Patient> findByNameContainingIgnoreCase(String name);
}

