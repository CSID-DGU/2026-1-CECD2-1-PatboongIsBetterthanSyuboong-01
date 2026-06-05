package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.PaginatedResponse;
import com.example.bitcomputer.service.DiseaseService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class DiseaseControllerTest {

    MockMvc mockMvc;

    @Mock
    DiseaseService diseaseService;

    @InjectMocks
    DiseaseController diseaseController;

    @BeforeEach
    void setup() {
        mockMvc = MockMvcBuilders.standaloneSetup(diseaseController).build();
    }

    @Nested
    @DisplayName("GET /api/diseases/{id}")
    class GetById {
        @Test
        @DisplayName("존재하면 200 OK + DTO 반환")
        void success() throws Exception {
            DiseaseDTO dto = new DiseaseDTO();
            dto.setId(1);
            dto.setCode("J00");
            dto.setName("급성 비인두염");
            dto.setNameEn("Acute nasopharyngitis");
            when(diseaseService.getById(eq(1))).thenReturn(dto);

            mockMvc.perform(get("/api/diseases/1"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(1))
                    .andExpect(jsonPath("$.code").value("J00"))
                    .andExpect(jsonPath("$.name").value("급성 비인두염"))
                    .andExpect(jsonPath("$.nameEn").value("Acute nasopharyngitis"));
        }

        @Test
        @DisplayName("없으면 404 Not Found")
        void notFound() throws Exception {
            when(diseaseService.getById(eq(999))).thenThrow(new jakarta.persistence.EntityNotFoundException("Disease not found with id 999"));

            mockMvc.perform(get("/api/diseases/999"))
                    .andExpect(status().isNotFound());
        }
    }

    @Nested
    @DisplayName("GET /api/diseases?query=... / code=... / name=...")
    class Search {
        @Test
        @DisplayName("query로 code/name 부분검색")
        void search_by_query() throws Exception {
            DiseaseDTO dto = new DiseaseDTO();
            dto.setId(1);
            dto.setCode("J00");
            dto.setName("급성 비인두염");
            PaginatedResponse<DiseaseDTO> response = new PaginatedResponse<>(List.of(dto), 1, 0, 50);
            when(diseaseService.search(eq("J0"), eq(null), eq(null), anyInt(), anyInt())).thenReturn(response);

            mockMvc.perform(get("/api/diseases").param("query", "J0"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.items[0].code").value("J00"));
        }

        @Test
        @DisplayName("code/name 조합으로 부분검색")
        void search_by_code_name() throws Exception {
            DiseaseDTO dto = new DiseaseDTO();
            dto.setId(1);
            dto.setCode("J00");
            dto.setName("급성 비인두염");
            PaginatedResponse<DiseaseDTO> response = new PaginatedResponse<>(List.of(dto), 1, 0, 50);
            when(diseaseService.search(eq(null), eq("J0"), eq("비인두"), anyInt(), anyInt())).thenReturn(response);

            mockMvc.perform(get("/api/diseases").param("code", "J0").param("name", "비인두"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.items[0].name").value("급성 비인두염"));
        }
    }
}