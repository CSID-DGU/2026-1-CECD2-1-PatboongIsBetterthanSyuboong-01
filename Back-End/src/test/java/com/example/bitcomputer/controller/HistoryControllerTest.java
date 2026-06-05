package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.service.HistoryService;
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

import java.util.Date;
import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class HistoryControllerTest {

    MockMvc mockMvc;

    ObjectMapper objectMapper;

    @Mock
    HistoryService historyService;

    @InjectMocks
    HistoryController historyController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(historyController).build();
    }

    @Nested
    @DisplayName("POST /api/histories/write_history")
    class WriteHistory {
        @Test
        @DisplayName("성공 시 200 OK + DTO 반환")
        void write_success() throws Exception {
            HistoryDTO saved = new HistoryDTO();
            saved.setId(1); saved.setEmployeeId(1); saved.setPatientId(2); saved.setDeptId(3);
            when(historyService.writeHistory(any(HistoryDTO.class))).thenReturn(saved);

            HistoryDTO req = new HistoryDTO();
            req.setEmployeeId(1); req.setPatientId(2); req.setDeptId(3); req.setEntryDate(new Date());

            mockMvc.perform(post("/api/histories/write_history")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(req)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(1));
        }
    }

    @Nested
    @DisplayName("PUT /api/histories/modify_history/{id}")
    class ModifyHistory {
        @Test
        @DisplayName("성공 시 200 OK + DTO 반환")
        void modify_success() throws Exception {
            HistoryDTO updated = new HistoryDTO();
            updated.setId(10);
            when(historyService.updateHistory(eq(10), any(HistoryDTO.class))).thenReturn(updated);

            HistoryDTO req = new HistoryDTO();
            req.setMemo("m");

            mockMvc.perform(put("/api/histories/modify_history/10")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(req)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(10));
        }
    }

    @Nested
    @DisplayName("GET /api/histories/search_history/{id}")
    class SearchHistory {
        @Test
        @DisplayName("start>end 이면 400 Bad Request")
        void search_bad_request() throws Exception {
            mockMvc.perform(get("/api/histories/search_history/1")
                            .param("patientId", "1")
                            .param("startDate", "2025-02-02")
                            .param("endDate", "2025-01-01"))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("정상 조회 시 200 OK + Map 반환")
        void search_success() throws Exception {
            when(historyService.searchHistory(eq(2), any(), any()))
                    .thenReturn(Map.of("patientId", 2, "histories", java.util.List.of()));

            mockMvc.perform(get("/api/histories/search_history/1")
                            .param("patientId", "2"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.patientId").value(2));
        }
    }
}
