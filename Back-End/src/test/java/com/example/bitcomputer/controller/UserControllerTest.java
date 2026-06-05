package com.example.bitcomputer.controller;

import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.LoginRequestDTO;
import com.example.bitcomputer.model.UserRegisterDTO;
import com.example.bitcomputer.service.UserService;
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

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class UserControllerTest {

    MockMvc mockMvc;

    ObjectMapper objectMapper;

    @Mock
    UserService userService;

    @Mock
    JwtTokenProvider jwtTokenProvider;

    @InjectMocks
    UserController userController;

    @BeforeEach
    void setup() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders.standaloneSetup(userController).build();
    }

    @Nested
    @DisplayName("POST /api/user/register")
    class Register {
        @Test
        @DisplayName("성공 시 201 Created")
        void register_success() throws Exception {
            doNothing().when(userService).registerUser(any(UserRegisterDTO.class));
            UserRegisterDTO dto = new UserRegisterDTO();
            dto.setName("n"); dto.setDeptId(1); dto.setRole("r"); dto.setUsername("u"); dto.setPassword("p");
            mockMvc.perform(post("/api/user/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isCreated());
        }

        @Test
        @DisplayName("중복 사용자 시 409 Conflict")
        void register_conflict() throws Exception {
            doThrow(new IllegalArgumentException("Username already exists")).when(userService).registerUser(any(UserRegisterDTO.class));
            UserRegisterDTO dto = new UserRegisterDTO();
            dto.setName("n"); dto.setDeptId(1); dto.setRole("r"); dto.setUsername("u"); dto.setPassword("p");
            mockMvc.perform(post("/api/user/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isConflict());
        }
    }

    @Nested
    @DisplayName("POST /api/user/login")
    class Login {
        @Test
        @DisplayName("정상 로그인 시 200 OK + TokenInfo")
        void login_success() throws Exception {
            TokenInfo token = TokenInfo.builder().grantType("Bearer").accessToken("a").refreshToken("r").build();
            when(userService.loginUser(any(LoginRequestDTO.class))).thenReturn(token);
            LoginRequestDTO dto = new LoginRequestDTO();
            dto.setUsername("u"); dto.setPassword("p");
            mockMvc.perform(post("/api/user/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.accessToken").value("a"))
                    .andExpect(jsonPath("$.refreshToken").value("r"));
        }

        @Test
        @DisplayName("인증 실패 시 401 Unauthorized")
        void login_unauthorized() throws Exception {
            when(userService.loginUser(any(LoginRequestDTO.class))).thenReturn(null);
            LoginRequestDTO dto = new LoginRequestDTO();
            dto.setUsername("u"); dto.setPassword("bad");
            mockMvc.perform(post("/api/user/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(dto)))
                    .andExpect(status().isUnauthorized());
        }
    }

    @Nested
    @DisplayName("POST /api/user/logout")
    class Logout {
        @Test
        @DisplayName("정상 로그아웃 시 200 OK")
        void logout_success() throws Exception {
            doNothing().when(userService).logoutUser(any());
            when(jwtTokenProvider.validateToken(eq("token"))).thenReturn(true);
            mockMvc.perform(post("/api/user/logout")
                            .header("Authorization", "Bearer token"))
                    .andExpect(status().isOk());
        }

        @Test
        @DisplayName("유효하지 않은 토큰이면 401")
        void logout_invalid_token_unauthorized() throws Exception {
            when(jwtTokenProvider.validateToken(eq("bad"))).thenReturn(false);
            mockMvc.perform(post("/api/user/logout")
                            .header("Authorization", "Bearer bad"))
                    .andExpect(status().isUnauthorized());
        }
    }
}
