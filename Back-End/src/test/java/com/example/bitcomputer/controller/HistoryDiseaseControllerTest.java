package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.HistoryDiseaseDTO;
import com.example.bitcomputer.service.HistoryDiseaseService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class HistoryDiseaseControllerTest {

    MockMvc mockMvc;
    ObjectMapper objectMapper;

    @Mock
    HistoryDiseaseService historyDiseaseService;

    @InjectMocks
    HistoryDiseaseController historyDiseaseController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(historyDiseaseController).build();
    }

    @Nested
    @DisplayName("PUT /api/histories/{historyId}/set_diseases")
    class SetDiseases {
        @Test
        @DisplayName("성공 시 200 OK + 목록 반환")
        void success() throws Exception {
            HistoryDiseaseDTO d1 = new HistoryDiseaseDTO(); d1.setId(1); d1.setHistoryId(10); d1.setCode("J00"); d1.setName("급성 비인두염");
            when(historyDiseaseService.setDiseasesForHistory(eq(1), eq(10), any())).thenReturn(List.of(d1));

            List<HistoryDiseaseDTO> req = List.of(d1);

            mockMvc.perform(put("/api/histories/10/set_diseases").param("employeeId", "1")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(req)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[0].id").value(1))
                    .andExpect(jsonPath("$[0].code").value("J00"));
        }
    }

    @Nested
    @DisplayName("GET /api/histories/{historyId}/get_diseases")
    class GetDiseases {
        @Test
        @DisplayName("성공 시 200 OK + 목록 반환")
        void success() throws Exception {
            HistoryDiseaseDTO d1 = new HistoryDiseaseDTO(); d1.setId(1); d1.setHistoryId(10); d1.setCode("J00"); d1.setName("급성 비인두염");
            when(historyDiseaseService.getDiseasesForHistory(eq(1), eq(10))).thenReturn(List.of(d1));

            mockMvc.perform(get("/api/histories/10/get_diseases").param("employeeId", "1"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[0].id").value(1))
                    .andExpect(jsonPath("$[0].name").value("급성 비인두염"));
        }
    }

    @Nested
    @DisplayName("POST /api/histories/{historyId}/add_disease/{diseaseId}")
    class AddDiseaseById {
        @Test
        @DisplayName("성공 시 201 Created + 질병 반환")
        void success() throws Exception {
            HistoryDiseaseDTO saved = new HistoryDiseaseDTO();
            saved.setId(99); saved.setHistoryId(10); saved.setCode("J00"); saved.setName("급성 비인두염");
            when(historyDiseaseService.addDiseaseById(eq(1), eq(10), eq(5), eq("PRIMARY"))).thenReturn(saved);

            mockMvc.perform(post("/api/histories/10/add_disease/5").param("employeeId", "1")
                            .param("degree", "PRIMARY"))
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.id").value(99))
                    .andExpect(jsonPath("$.code").value("J00"));
        }
    }
}