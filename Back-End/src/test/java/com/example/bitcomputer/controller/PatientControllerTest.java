package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.PatientDTO;
import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.model.WriteHistoryDTO;
import com.example.bitcomputer.service.PatientService;
import com.example.bitcomputer.service.HistoryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class PatientControllerTest {

    MockMvc mockMvc;

    ObjectMapper objectMapper;

    @Mock
    PatientService patientService;

    @Mock
    HistoryService historyService;

    @InjectMocks
    PatientController patientController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(patientController).build();
    }

    @Test
    @DisplayName("성공 시 201 Created와 patientId 반환")
    void create_success() throws Exception {
        PatientDTO saved = new PatientDTO();
        saved.setId(123);
        when(patientService.createPatient(any(PatientDTO.class))).thenReturn(saved);

        PatientDTO req = new PatientDTO();
        req.setName("홍길동");
        req.setPhoneNumber("010");
        req.setIdentityNumber("900101-1234567");
        req.setGender("M");
        req.setBirth(new java.util.Date());

        mockMvc.perform(post("/api/patients/get_patient_id")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.patientId").value(123));
    }

    

    @Test
    @DisplayName("/search_patient/{id} 정상 반환")
    void search_patient_success() throws Exception {
        PatientDTO dto = new PatientDTO();
        dto.setId(7);
        dto.setName("홍길동");
        dto.setIdentityNumber("900101-1234567");
        when(patientService.searchPatientById(7)).thenReturn(dto);
        mockMvc.perform(post("/api/patients/search_patient/7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(7))
                .andExpect(jsonPath("$.identityNumber").value("900101-1234567"));
    }

    @Test
    @DisplayName("/search_history/{id} startDate > endDate면 400 Bad Request")
    void search_history_badRequest_whenStartAfterEnd() throws Exception {
        mockMvc.perform(post("/api/patients/search_history/1")
                        .param("patientId", "2")
                        .param("startDate", "2025-02-02")
                        .param("endDate", "2025-01-01"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("/search_history/{id} 정상 조회 시 200 OK + Map 반환")
    void search_history_success() throws Exception {
        when(historyService.searchHistory(eq(2), any(), any()))
                .thenReturn(Map.of("patientId", 2, "histories", List.of()));
        
        mockMvc.perform(post("/api/patients/search_history/1")
                        .param("patientId", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.patientId").value(2));
    }

    @Test
    @DisplayName("/update_history/{id} WriteHistoryDTO 요청 정상 반환")
    void update_history_with_writeDto_success() throws Exception {
        WriteHistoryDTO req = new WriteHistoryDTO();
        req.setMemo("m");
        HistoryDTO res = new HistoryDTO(); res.setId(77);
        when(historyService.updateHistory(eq(77), any(WriteHistoryDTO.class))).thenReturn(res);
        mockMvc.perform(post("/api/patients/update_history/77")
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(77));
    }
}
