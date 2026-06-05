package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.WaitingRepository;
import com.example.bitcomputer.entity.Waiting;
import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.WaitingDTO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class WaitingServiceImplTest {
    @Mock
    WaitingRepository waitingRepository;

    @Mock
    JwtTokenProvider jwtTokenProvider;

    @InjectMocks
    WaitingServiceImpl waitingService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Nested
    @DisplayName("registerWaiting")
    class RegisterWaitingTest {
        @Test
        @DisplayName("성공적으로 저장 및 토큰 반환")
        void register_success() {
            Waiting waiting = new Waiting();
            waiting.setPatientId(1);
            waiting.setSymptom("aa");
            waiting.setEntryDate(LocalDateTime.now());
            waiting.setState("waiting");
            // 저장 후 반환(Mock)
            when(waitingRepository.save(any(Waiting.class))).thenReturn(waiting);
            when(jwtTokenProvider.generateAccessToken(anyString())).thenReturn("access");
            when(jwtTokenProvider.generateRefreshToken(anyString())).thenReturn("refresh");
            // DTO
            WaitingDTO dto = new WaitingDTO();
            dto.setPatientId(1);
            dto.setSymptom("aa");
            TokenInfo token = waitingService.registerWaiting(dto);
            assertThat(token.getAccessToken()).isEqualTo("access");
            assertThat(token.getRefreshToken()).isEqualTo("refresh");
            assertThat(token.getGrantType()).isEqualTo("Bearer");
            verify(waitingRepository).save(any(Waiting.class));
            verify(jwtTokenProvider).generateAccessToken(anyString());
            verify(jwtTokenProvider).generateRefreshToken(anyString());
        }
    }
    @Nested
    @DisplayName("getWaitingList")
    class GetWaitingListTest {
        @Test
        @DisplayName("리스트 정상 반환")
        void get_list_success() {
            Waiting a = new Waiting();
            a.setId(1); a.setPatientId(1); a.setSymptom("a"); a.setEntryDate(LocalDateTime.now()); a.setState("waiting");
            Waiting b = new Waiting();
            b.setId(2); b.setPatientId(2); b.setSymptom("b"); b.setEntryDate(LocalDateTime.now()); b.setState("waiting");
            when(waitingRepository.findAll()).thenReturn(Arrays.asList(a, b));
            List<WaitingDTO> list = waitingService.getWaitingList();
            assertThat(list).hasSize(2);
            assertThat(list.get(0).getPatientId()).isEqualTo(1);
            assertThat(list.get(1).getPatientId()).isEqualTo(2);
        }
    }
    @Nested
    @DisplayName("updateWaitingState")
    class UpdateWaitingStateTest {
        @Test
        @DisplayName("정상적으로 상태 업데이트 및 토큰 반환")
        void update_success() {
            Waiting waiting = new Waiting();
            waiting.setId(1);
            waiting.setPatientId(1);
            waiting.setState("waiting");
            when(waitingRepository.findFirstByPatientIdOrderByIdDesc(eq(1))).thenReturn(Optional.of(waiting));
            when(waitingRepository.save(any(Waiting.class))).thenReturn(waiting);
            when(jwtTokenProvider.generateAccessToken(anyString())).thenReturn("a");
            when(jwtTokenProvider.generateRefreshToken(anyString())).thenReturn("r");
            TokenInfo token = waitingService.updateWaitingState(1);
            assertThat(token.getAccessToken()).isEqualTo("a");
            assertThat(token.getRefreshToken()).isEqualTo("r");
        }
        @Test
        @DisplayName("대기 정보 없으면 예외")
        void update_not_exist_throw() {
            when(waitingRepository.findFirstByPatientIdOrderByIdDesc(anyInt())).thenReturn(Optional.empty());
            assertThatThrownBy(() -> waitingService.updateWaitingState(99))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("대기 정보를 찾을 수 없습니다");
        }
    }
}
