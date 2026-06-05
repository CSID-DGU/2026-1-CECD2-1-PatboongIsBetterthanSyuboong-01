package com.example.bitcomputer.service;

import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.PaginatedResponse;

import java.io.File;
import java.util.List;

public interface DiseaseService {
    DiseaseDTO getById(int id);
    PaginatedResponse<DiseaseDTO> search(String query, String code, String name, int page, int size);
    int uploadFromExcel(File file);
}

