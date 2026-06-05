package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.service.HistoryService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Date;
import java.util.Map;

@RestController
@RequestMapping("/api/histories")
public class HistoryController {

    private final HistoryService historyService;

    public HistoryController(HistoryService historyService) {
        this.historyService = historyService;
    }

    @PostMapping("/write_history")
    public ResponseEntity<HistoryDTO> writeHistory(@RequestBody HistoryDTO request) {
        HistoryDTO saved = historyService.writeHistory(request);
        return ResponseEntity.ok(saved);
    }

    @PutMapping("/modify_history/{id}")
    public ResponseEntity<HistoryDTO> modifyHistory(@PathVariable int id,
                                                    @RequestBody HistoryDTO request) {
        HistoryDTO updated = historyService.updateHistory(id, request);
        return ResponseEntity.ok(updated);
    }

    //Description: 로그인한 직원이 조건에 따라 환자의 진료 기록을 검색. 검색 성공 시, 조건에 맞는 진료 기록 목록을 반환.
    @GetMapping("/search_history/{id}")
    public ResponseEntity<Map<String, Object>> searchHistory(
            @PathVariable("id") int employeeId,
            @RequestParam("patientId") int patientId,
            @RequestParam(value = "startDate", required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") Date startDate,
            @RequestParam(value = "endDate", required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") Date endDate) {

        if (startDate != null && endDate != null && startDate.after(endDate)) {
            return ResponseEntity.badRequest().build();
        }

        Map<String, Object> response = historyService.searchHistory(patientId, startDate, endDate);
        return ResponseEntity.ok(response);
    }
}

