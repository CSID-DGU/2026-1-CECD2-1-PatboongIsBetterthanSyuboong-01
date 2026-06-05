package com.example.bitcomputer.service;

import com.example.bitcomputer.model.HistoryDiseaseDTO;

import java.util.List;

public interface HistoryDiseaseService {
    List<HistoryDiseaseDTO> setDiseasesForHistory(int employeeId, int historyId, List<HistoryDiseaseDTO> diseases);
    List<HistoryDiseaseDTO> getDiseasesForHistory(int employeeId, int historyId);
    HistoryDiseaseDTO addDiseaseById(int employeeId, int historyId, int diseaseId, String degree);
}