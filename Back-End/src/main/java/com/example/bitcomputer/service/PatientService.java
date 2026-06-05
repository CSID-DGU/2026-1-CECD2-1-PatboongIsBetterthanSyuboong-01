package com.example.bitcomputer.service;

import com.example.bitcomputer.model.PatientDTO;
import com.example.bitcomputer.entity.Role;

import java.util.List;

public interface PatientService {
    PatientDTO createPatient(PatientDTO request);
    PatientDTO searchPatientById(int id);
    PatientDTO searchPatientByIdentityNumber(String identityNumber);
    List<PatientDTO> getAllPatients();
}

