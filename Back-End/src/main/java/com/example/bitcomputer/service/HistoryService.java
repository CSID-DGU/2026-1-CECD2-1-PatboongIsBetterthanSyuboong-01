package com.example.bitcomputer.service;

import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.model.WriteHistoryDTO;

import java.util.Date;
import java.util.Map;

public interface HistoryService {
    HistoryDTO writeHistory(HistoryDTO request);

    HistoryDTO updateHistory(int id, HistoryDTO request);

    Map<String, Object> searchHistory(int patientId, Date startDate, Date endDate);

    HistoryDTO writeHistory(WriteHistoryDTO request);

    HistoryDTO updateHistory(int id, WriteHistoryDTO request);
}

