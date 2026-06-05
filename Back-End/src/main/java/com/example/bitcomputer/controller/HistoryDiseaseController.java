package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.HistoryDiseaseDTO;
import com.example.bitcomputer.service.HistoryDiseaseService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/histories")
public class HistoryDiseaseController {

    private final HistoryDiseaseService historyDiseaseService;
    public HistoryDiseaseController(HistoryDiseaseService historyDiseaseService) {
        this.historyDiseaseService = historyDiseaseService;
    }

    @PutMapping("/{historyId}/set_diseases")
    public ResponseEntity<List<HistoryDiseaseDTO>> setDiseases(
            @PathVariable int historyId,
            @RequestParam("employeeId") int employeeId,
            @RequestBody List<HistoryDiseaseDTO> request
    ) {
        List<HistoryDiseaseDTO> saved = historyDiseaseService.setDiseasesForHistory(employeeId, historyId, request);
        return ResponseEntity.ok(saved);
    }

    @GetMapping("/{historyId}/get_diseases")
    public ResponseEntity<List<HistoryDiseaseDTO>> getDiseases(
            @PathVariable int historyId,
            @RequestParam("employeeId") int employeeId
    ) {
        return ResponseEntity.ok(historyDiseaseService.getDiseasesForHistory(employeeId, historyId));
    }

    @PostMapping("/{historyId}/add_disease/{diseaseId}")
    public ResponseEntity<HistoryDiseaseDTO> addDiseaseById(
            @PathVariable int historyId,
            @PathVariable int diseaseId,
            @RequestParam("employeeId") int employeeId,
            @RequestParam(value = "degree", required = false) String degree
    ) {
        HistoryDiseaseDTO saved = historyDiseaseService.addDiseaseById(employeeId, historyId, diseaseId, degree);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }
}


