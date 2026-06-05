package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.HistoryDiagnoseDTO;
import com.example.bitcomputer.service.HistoryDiagnoseService;
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
class HistoryDiagnoseControllerTest {

    MockMvc mockMvc;
    ObjectMapper objectMapper;

    @Mock
    HistoryDiagnoseService historyDiagnoseService;

    @InjectMocks
    HistoryDiagnoseController historyDiagnoseController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(historyDiagnoseController).build();
    }

    @Nested
    @DisplayName("PUT /api/histories/{historyId}/set_diagnoses")
    class SetDiagnoses {
        @Test
        @DisplayName("성공 시 200 OK + 목록 반환")
        void success() throws Exception {
            HistoryDiagnoseDTO d1 = new HistoryDiagnoseDTO();
            d1.setId(1); d1.setHistoryId(10); d1.setCode("D001"); d1.setName("타이레놀");
            d1.setDose(500); d1.setTime(3); d1.setDays(5);
            when(historyDiagnoseService.setDiagnosesForHistory(eq(1), eq(10), any())).thenReturn(List.of(d1));

            List<HistoryDiagnoseDTO> req = List.of(d1);

            mockMvc.perform(put("/api/histories/10/set_diagnoses").param("employeeId", "1")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(req)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[0].id").value(1))
                    .andExpect(jsonPath("$[0].code").value("D001"));
        }
    }

    @Nested
    @DisplayName("GET /api/histories/{historyId}/get_diagnoses")
    class GetDiagnoses {
        @Test
        @DisplayName("성공 시 200 OK + 목록 반환")
        void success() throws Exception {
            HistoryDiagnoseDTO d1 = new HistoryDiagnoseDTO();
            d1.setId(1); d1.setHistoryId(10); d1.setCode("D001"); d1.setName("타이레놀");
            d1.setDose(500); d1.setTime(3); d1.setDays(5);
            when(historyDiagnoseService.getDiagnosesForHistory(eq(1), eq(10))).thenReturn(List.of(d1));

            mockMvc.perform(get("/api/histories/10/get_diagnoses").param("employeeId", "1"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[0].id").value(1))
                    .andExpect(jsonPath("$[0].name").value("타이레놀"));
        }
    }

    @Nested
    @DisplayName("POST /api/histories/{historyId}/add_diagnose/{diagnoseId}")
    class AddDiagnoseById {
        @Test
        @DisplayName("성공 시 201 Created + 처방 반환")
        void success() throws Exception {
            HistoryDiagnoseDTO saved = new HistoryDiagnoseDTO();
            saved.setId(99); saved.setHistoryId(10); saved.setCode("D001"); saved.setName("타이레놀");
            saved.setDose(500); saved.setTime(3); saved.setDays(5);
            when(historyDiagnoseService.addDiagnoseById(eq(1), eq(10), eq(5))).thenReturn(saved);

            mockMvc.perform(post("/api/histories/10/add_diagnose/5").param("employeeId", "1"))
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.id").value(99))
                    .andExpect(jsonPath("$.code").value("D001"));
        }
    }
}

