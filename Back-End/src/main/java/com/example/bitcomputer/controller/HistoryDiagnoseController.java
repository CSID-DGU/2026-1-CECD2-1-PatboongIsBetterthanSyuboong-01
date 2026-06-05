package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.HistoryDiagnoseDTO;
import com.example.bitcomputer.service.HistoryDiagnoseService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/histories")
public class HistoryDiagnoseController {

    private final HistoryDiagnoseService historyDiagnoseService;

    public HistoryDiagnoseController(HistoryDiagnoseService historyDiagnoseService) {
        this.historyDiagnoseService = historyDiagnoseService;
    }

    @PutMapping("/{historyId}/set_diagnoses")
    public ResponseEntity<List<HistoryDiagnoseDTO>> setDiagnoses(
            @PathVariable int historyId,
            @RequestParam("employeeId") int employeeId,
            @RequestBody List<HistoryDiagnoseDTO> request
    ) {
        List<HistoryDiagnoseDTO> saved = historyDiagnoseService.setDiagnosesForHistory(employeeId, historyId, request);
        return ResponseEntity.ok(saved);
    }

    @GetMapping("/{historyId}/get_diagnoses")
    public ResponseEntity<List<HistoryDiagnoseDTO>> getDiagnoses(
            @PathVariable int historyId,
            @RequestParam("employeeId") int employeeId
    ) {
        return ResponseEntity.ok(historyDiagnoseService.getDiagnosesForHistory(employeeId, historyId));
    }

    @PostMapping("/{historyId}/add_diagnose/{diagnoseId}")
    public ResponseEntity<HistoryDiagnoseDTO> addDiagnoseById(
            @PathVariable int historyId,
            @PathVariable int diagnoseId,
            @RequestParam("employeeId") int employeeId
    ) {
        HistoryDiagnoseDTO saved = historyDiagnoseService.addDiagnoseById(employeeId, historyId, diagnoseId);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }
}

