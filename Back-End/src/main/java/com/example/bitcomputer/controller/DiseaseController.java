package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.PaginatedResponse;
import com.example.bitcomputer.service.DiseaseService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/diseases")
public class DiseaseController {

    private final DiseaseService diseaseService;

    public DiseaseController(DiseaseService diseaseService) {
        this.diseaseService = diseaseService;
    }

    @GetMapping("/{id}")
    public ResponseEntity<DiseaseDTO> getById(@PathVariable int id) {
        try {
            DiseaseDTO dto = diseaseService.getById(id);
            return ResponseEntity.ok(dto);
        } catch (jakarta.persistence.EntityNotFoundException e) {
            return ResponseEntity.notFound().build();
        }
    }

    @GetMapping
    public ResponseEntity<PaginatedResponse<DiseaseDTO>> search(
            @RequestParam(value = "query", required = false) String query,
            @RequestParam(value = "code", required = false) String code,
            @RequestParam(value = "name", required = false) String name,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "50") int size
    ) {
        PaginatedResponse<DiseaseDTO> result = diseaseService.search(query, code, name, page, size);
        return ResponseEntity.ok(result);
    }
}