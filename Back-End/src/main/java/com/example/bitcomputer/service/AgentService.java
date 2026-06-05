package com.example.bitcomputer.service;

import com.example.bitcomputer.model.PrescriptionRecommendRequestDTO;
import com.example.bitcomputer.model.SavePrescriptionFeedbackRequestDTO;
import com.example.bitcomputer.model.ValidationJobStartResponseDTO;

public interface AgentService {

    ValidationJobStartResponseDTO recommendPrescription(PrescriptionRecommendRequestDTO request);

    void savePrescriptionFeedback(SavePrescriptionFeedbackRequestDTO request);
}
