package com.example.bitcomputer.controller;

import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.WaitingDTO;
import com.example.bitcomputer.service.WaitingService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class WaitingControllerTest {

    private MockMvc mockMvc;

    private ObjectMapper objectMapper;

    @Mock
    private WaitingService waitingService;

    @InjectMocks
    private WaitingController waitingController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(waitingController).build();
    }

    @Nested
    @DisplayName("POST /api/waiting/register")
    class RegisterWaitingTests {
        @Test
        @DisplayName("정상 요청 시 200 OK와 TokenInfo 반환")
        void register_success() throws Exception {
            TokenInfo token = TokenInfo.builder()
                    .grantType("Bearer")
                    .accessToken("access")
                    .refreshToken("refresh")
                    .build();
            when(waitingService.registerWaiting(any(WaitingDTO.class))).thenReturn(token);

            WaitingDTO dto = new WaitingDTO();
            dto.setPatientId(1);

            mockMvc.perform(post("/api/waiting/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.accessToken", is("access")))
                    .andExpect(jsonPath("$.refreshToken", is("refresh")));
        }

        @Test
        @DisplayName("patientId<=0 이면 400 Bad Request")
        void register_badRequest_onInvalidPatientId() throws Exception {
            WaitingDTO dto = new WaitingDTO();
            dto.setPatientId(0);

            mockMvc.perform(post("/api/waiting/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("서비스가 IllegalArgumentException 던지면 400 Bad Request")
        void register_badRequest_onIllegalArgument() throws Exception {
            when(waitingService.registerWaiting(any(WaitingDTO.class)))
                    .thenThrow(new IllegalArgumentException("invalid"));

            WaitingDTO dto = new WaitingDTO();
            dto.setPatientId(1);

            mockMvc.perform(post("/api/waiting/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("GET /api/waiting/get_list")
    class GetListTests {
        @Test
        @DisplayName("목록이 존재하면 200 OK와 리스트 반환")
        void getList_returnsItems() throws Exception {
            WaitingDTO a = new WaitingDTO();
            a.setPatientId(1);
            WaitingDTO b = new WaitingDTO();
            b.setPatientId(2);
            List<WaitingDTO> list = Arrays.asList(a, b);
            when(waitingService.getWaitingList()).thenReturn(list);

            mockMvc.perform(get("/api/waiting/get_list"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$", hasSize(2)));
        }

        @Test
        @DisplayName("빈 목록도 200 OK로 반환")
        void getList_returnsEmptyList() throws Exception {
            when(waitingService.getWaitingList()).thenReturn(Collections.emptyList());

            mockMvc.perform(get("/api/waiting/get_list"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$", hasSize(0)));
        }

        @Test
        @DisplayName("서비스 예외 시 500 Internal Server Error")
        void getList_internalServerError_onException() throws Exception {
            when(waitingService.getWaitingList()).thenThrow(new RuntimeException("boom"));

            mockMvc.perform(get("/api/waiting/get_list"))
                    .andExpect(status().isInternalServerError());
        }
    }

    @Nested
    @DisplayName("PUT /api/waiting/{patientid}/complete")
    class UpdateWaitingStateTests {
        @Test
        @DisplayName("patientid<=0 이면 400 Bad Request")
        void update_badRequest_onInvalidId() throws Exception {
            mockMvc.perform(put("/api/waiting/0/complete"))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("서비스가 정상 응답을 주는 경우(오타 수정 시) 200 OK")
        void update_success_assumingFixedBinding() throws Exception {
            TokenInfo token = TokenInfo.builder()
                    .grantType("Bearer")
                    .accessToken("ok")
                    .refreshToken("r")
                    .build();
            when(waitingService.updateWaitingState(Mockito.eq(1))).thenReturn(token);

            mockMvc.perform(put("/api/waiting/1/complete"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.accessToken").value("ok"))
                    .andExpect(jsonPath("$.refreshToken").value("r"));
        }

        @Test
        @DisplayName("서비스가 null 반환 시 401 Unauthorized")
        void update_unauthorized_whenServiceReturnsNull() throws Exception {
            when(waitingService.updateWaitingState(Mockito.eq(2))).thenReturn(null);
            mockMvc.perform(put("/api/waiting/2/complete"))
                    .andExpect(status().isUnauthorized());
        }
    }
}


