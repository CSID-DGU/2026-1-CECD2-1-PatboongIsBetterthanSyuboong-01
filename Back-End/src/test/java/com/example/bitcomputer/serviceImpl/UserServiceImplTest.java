package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.UserRepository;
import com.example.bitcomputer.entity.Employee;
import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.LoginRequestDTO;
import com.example.bitcomputer.model.UserRegisterDTO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.security.crypto.password.PasswordEncoder;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class UserServiceImplTest {

    @Mock
    UserRepository userRepository;
    @Mock
    PasswordEncoder passwordEncoder;
    @Mock
    JwtTokenProvider jwtTokenProvider;
    @Mock
    TokenBlacklistService tokenBlacklistService;

    @InjectMocks
    UserServiceImpl userService;

    @BeforeEach
    void setUp() { MockitoAnnotations.openMocks(this); }

    @Nested
    @DisplayName("registerUser")
    class Register {
        @Test
        @DisplayName("중복 사용자면 예외")
        void duplicate_username() {
            when(userRepository.findByUsername(eq("dup"))).thenReturn(new Employee());
            UserRegisterDTO dto = new UserRegisterDTO();
            dto.setUsername("dup"); dto.setPassword("p"); dto.setName("n"); dto.setDeptId(1); dto.setRole("DOCTOR");
            assertThatThrownBy(() -> userService.registerUser(dto))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("exists");
        }

        @Test
        @DisplayName("성공 시 저장 수행")
        void register_success() {
            when(userRepository.findByUsername(anyString())).thenReturn(null);
            when(passwordEncoder.encode(anyString())).thenReturn("enc");
            UserRegisterDTO dto = new UserRegisterDTO();
            dto.setUsername("ok"); dto.setPassword("p"); dto.setName("n"); dto.setDeptId(1); dto.setRole("DOCTOR");
            userService.registerUser(dto);
            verify(userRepository).save(any(Employee.class));
        }
    }

    @Nested
    @DisplayName("loginUser")
    class Login {
        @Test
        @DisplayName("아이디 없음/비번 불일치 시 예외")
        void invalid_credentials() {
            when(userRepository.findByUsername(eq("u"))).thenReturn(null);
            LoginRequestDTO dto = new LoginRequestDTO(); dto.setUsername("u"); dto.setPassword("p");
            assertThatThrownBy(() -> userService.loginUser(dto))
                    .isInstanceOf(IllegalArgumentException.class);
        }

        @Test
        @DisplayName("성공 시 토큰 반환")
        void login_success() {
            Employee e = new Employee(); e.setUsername("u"); e.setPassword("hash");
            when(userRepository.findByUsername(eq("u"))).thenReturn(e);
            when(passwordEncoder.matches(eq("p"), eq("hash"))).thenReturn(true);
            when(jwtTokenProvider.generateAccessToken(eq("u"))).thenReturn("a");
            when(jwtTokenProvider.generateRefreshToken(eq("u"))).thenReturn("r");
            LoginRequestDTO dto = new LoginRequestDTO(); dto.setUsername("u"); dto.setPassword("p");
            TokenInfo token = userService.loginUser(dto);
            assertThat(token.getAccessToken()).isEqualTo("a");
            assertThat(token.getRefreshToken()).isEqualTo("r");
        }
    }

    @Nested
    @DisplayName("logoutUser")
    class Logout {
        @Test
        @DisplayName("남은 시간이 양수면 블랙리스트 호출")
        void blacklist_called_on_positive_exp() {
            when(jwtTokenProvider.getExpiration(eq("token"))).thenReturn(System.currentTimeMillis() + 10_000);
            userService.logoutUser("token");
            org.mockito.ArgumentCaptor<Long> captor = org.mockito.ArgumentCaptor.forClass(Long.class);
            verify(tokenBlacklistService).blacklistToken(eq("token"), captor.capture());
            assertThat(captor.getValue()).isPositive();
        }

        @Test
        @DisplayName("만료 시간 경과 시 블랙리스트 미호출")
        void blacklist_not_called_on_past_exp() {
            when(jwtTokenProvider.getExpiration(eq("token"))).thenReturn(System.currentTimeMillis() - 1_000);
            userService.logoutUser("token");
            verify(tokenBlacklistService, never()).blacklistToken(anyString(), anyLong());
        }
    }
}
