package com.example.bitcomputer.service;

import com.example.bitcomputer.model.DiagnoseDTO;
import com.example.bitcomputer.model.PaginatedResponse;

import java.io.File;

public interface DiagnoseService {
    DiagnoseDTO getById(int id);
    PaginatedResponse<DiagnoseDTO> search(String query, String code, String name, int page, int size);
    int uploadFromExcel(File file);
}

