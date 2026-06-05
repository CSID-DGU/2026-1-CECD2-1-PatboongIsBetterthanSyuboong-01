package com.example.bitcomputer.service;

import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.WaitingDTO;

import java.util.List;

public interface WaitingService {
    TokenInfo registerWaiting(WaitingDTO waitingDTO);
    List<WaitingDTO> getWaitingList();
    TokenInfo updateWaitingState(int patientId);
    TokenInfo updateWaitingStateToHold(int patientId);
    TokenInfo updateWaitingStateByWaitingId(int waitingId);
    TokenInfo updateWaitingStateToHoldByWaitingId(int waitingId);
    void deleteWaitingByWaitingId(int waitingId);
}
