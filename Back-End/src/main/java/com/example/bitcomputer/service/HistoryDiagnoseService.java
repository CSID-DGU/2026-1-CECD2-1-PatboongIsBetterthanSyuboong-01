package com.example.bitcomputer.service;

import com.example.bitcomputer.model.HistoryDiagnoseDTO;

import java.util.List;

public interface HistoryDiagnoseService {
    List<HistoryDiagnoseDTO> setDiagnosesForHistory(int employeeId, int historyId, List<HistoryDiagnoseDTO> diagnoses);
    List<HistoryDiagnoseDTO> getDiagnosesForHistory(int employeeId, int historyId);
    HistoryDiagnoseDTO addDiagnoseById(int employeeId, int historyId, int diagnoseId);
}

