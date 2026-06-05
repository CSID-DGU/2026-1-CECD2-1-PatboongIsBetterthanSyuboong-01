package com.example.bitcomputer.controller;

import com.example.bitcomputer.model.DiagnoseDTO;
import com.example.bitcomputer.model.PaginatedResponse;
import com.example.bitcomputer.service.DiagnoseService;
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
class DiagnoseControllerTest {

    MockMvc mockMvc;

    @Mock
    DiagnoseService diagnoseService;

    @InjectMocks
    DiagnoseController diagnoseController;

    @BeforeEach
    void setup() {
        mockMvc = MockMvcBuilders.standaloneSetup(diagnoseController).build();
    }

    @Nested
    @DisplayName("GET /api/diagnoses/{id}")
    class GetById {
        @Test
        @DisplayName("존재하면 200 OK + DTO 반환")
        void success() throws Exception {
            DiagnoseDTO dto = new DiagnoseDTO();
            dto.setId(1);
            dto.setCode("D001");
            dto.setName("타이레놀");
            dto.setDose(500);
            dto.setTime(3);
            dto.setDays(5);
            when(diagnoseService.getById(eq(1))).thenReturn(dto);

            mockMvc.perform(get("/api/diagnoses/1"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(1))
                    .andExpect(jsonPath("$.code").value("D001"))
                    .andExpect(jsonPath("$.name").value("타이레놀"))
                    .andExpect(jsonPath("$.dose").value(500))
                    .andExpect(jsonPath("$.time").value(3))
                    .andExpect(jsonPath("$.days").value(5));
        }

        @Test
        @DisplayName("없으면 404 Not Found")
        void notFound() throws Exception {
            when(diagnoseService.getById(eq(999))).thenThrow(new jakarta.persistence.EntityNotFoundException("Diagnose not found with id 999"));

            mockMvc.perform(get("/api/diagnoses/999"))
                    .andExpect(status().isNotFound());
        }
    }

    @Nested
    @DisplayName("GET /api/diagnoses?query=... / code=... / name=...")
    class Search {
        @Test
        @DisplayName("query로 코드/이름 부분검색")
        void search_by_query() throws Exception {
            DiagnoseDTO dto = new DiagnoseDTO();
            dto.setId(1);
            dto.setCode("D001");
            dto.setName("타이레놀");
            dto.setDose(500);
            dto.setTime(3);
            dto.setDays(5);
            PaginatedResponse<DiagnoseDTO> response = new PaginatedResponse<>(List.of(dto), 1, 0, 50);
            when(diagnoseService.search(eq("타이"), eq(null), eq(null), anyInt(), anyInt())).thenReturn(response);

            mockMvc.perform(get("/api/diagnoses").param("query", "타이"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.items[0].code").value("D001"));
        }

        @Test
        @DisplayName("code/name 조합으로 부분검색")
        void search_by_code_name() throws Exception {
            DiagnoseDTO dto = new DiagnoseDTO();
            dto.setId(1);
            dto.setCode("D001");
            dto.setName("타이레놀");
            dto.setDose(500);
            dto.setTime(3);
            dto.setDays(5);
            PaginatedResponse<DiagnoseDTO> response = new PaginatedResponse<>(List.of(dto), 1, 0, 50);
            when(diagnoseService.search(eq(null), eq("D0"), eq("타이레놀"), anyInt(), anyInt())).thenReturn(response);

            mockMvc.perform(get("/api/diagnoses").param("code", "D0").param("name", "타이레놀"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.items[0].name").value("타이레놀"));
        }
    }
}

