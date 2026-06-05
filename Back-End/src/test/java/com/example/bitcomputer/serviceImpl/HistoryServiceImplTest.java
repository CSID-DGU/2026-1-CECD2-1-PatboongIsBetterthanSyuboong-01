package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.PatientRepository;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.Patient;
import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.model.WriteHistoryDTO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import jakarta.persistence.EntityNotFoundException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.Date;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class HistoryServiceImplTest {

    @Mock
    HistoryRepository historyRepository;
    @Mock
    PatientRepository patientRepository;

    @InjectMocks
    HistoryServiceImpl historyService;

    @BeforeEach
    void setUp() { MockitoAnnotations.openMocks(this); }

    @Nested
    @DisplayName("writeHistory")
    class Write {
        @Test
        @DisplayName("저장 후 DTO 반환")
        void write_success() {
            History saved = new History(); saved.setId(1);
            when(historyRepository.save(any(History.class))).thenReturn(saved);
            HistoryDTO req = new HistoryDTO();
            req.setEmployeeId(1); req.setPatientId(2); req.setDeptId(3); req.setEntryDate(new Date());
            HistoryDTO res = historyService.writeHistory(req);
            assertThat(res.getId()).isEqualTo(1);
        }
    }

    @Nested
    @DisplayName("updateHistory")
    class Update {
        @Test
        @DisplayName("존재하지 않으면 예외")
        void not_found() {
            when(historyRepository.findById(eq(99))).thenReturn(Optional.empty());
            assertThatThrownBy(() -> historyService.updateHistory(99, new HistoryDTO()))
                    .isInstanceOf(EntityNotFoundException.class);
        }

        @Test
        @DisplayName("일부 필드 수정 후 저장")
        void update_success() {
            History h = new History(); h.setId(5);
            when(historyRepository.findById(eq(5))).thenReturn(Optional.of(h));
            when(historyRepository.save(any(History.class))).thenAnswer(i -> i.getArgument(0));
            HistoryDTO req = new HistoryDTO(); req.setMemo("m");
            HistoryDTO res = historyService.updateHistory(5, req);
            assertThat(res.getId()).isEqualTo(5);
        }
    }

    @Nested
    @DisplayName("searchHistory(id)")
    class SearchById {
        @Test
        @DisplayName("환자/진료 기록 모두 존재 시 DTO 반환")
        void success() {
            com.example.bitcomputer.entity.Patient p = new com.example.bitcomputer.entity.Patient(); p.setId(10);
            when(patientRepository.findById(eq(10))).thenReturn(java.util.Optional.of(p));
            History h = new History(); h.setId(10);
            when(historyRepository.findById(eq(10))).thenReturn(java.util.Optional.of(h));
            java.util.Map<String, Object> res = historyService.searchHistory(10, null, null);
            assertThat(res).containsKeys("histories");
        }

        @Test
        @DisplayName("환자 없으면 예외")
        void no_patient() {
            when(patientRepository.findById(eq(9))).thenReturn(java.util.Optional.empty());
            assertThatThrownBy(() -> historyService.searchHistory(9, null, null))
                    .isInstanceOf(jakarta.persistence.EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("writeHistory(WriteHistoryDTO)")
    class WriteWithWriteDto {
        @Test
        @DisplayName("매핑 후 저장, DTO 반환")
        void success() {
            when(historyRepository.save(any(History.class))).thenAnswer(i -> { History hh = i.getArgument(0); hh.setId(1); return hh;});
            WriteHistoryDTO req = new WriteHistoryDTO();
            req.setEmployeeId(1); req.setPatientId(2); req.setDeptId(3);
            HistoryDTO res = historyService.writeHistory(req);
            assertThat(res.getId()).isEqualTo(1);
        }
    }

    @Nested
    @DisplayName("updateHistory(id, WriteHistoryDTO)")
    class UpdateWithWriteDto {
        @Test
        @DisplayName("기록 없으면 예외")
        void not_found() {
            when(historyRepository.findById(eq(100))).thenReturn(java.util.Optional.empty());
            assertThatThrownBy(() -> historyService.updateHistory(100, new WriteHistoryDTO()))
                    .isInstanceOf(jakarta.persistence.EntityNotFoundException.class);
        }
    }
    @Nested
    @DisplayName("searchHistory")
    class Search {
        @Test
        @DisplayName("환자 없으면 예외")
        void no_patient() {
            when(patientRepository.findById(eq(1))).thenReturn(Optional.empty());
            assertThatThrownBy(() -> historyService.searchHistory(1, null, null))
                    .isInstanceOf(EntityNotFoundException.class);
        }

        @Test
        @DisplayName("정상 조회 시 Map 반환")
        void success() {
            Patient p = new Patient(); p.setId(2); p.setName("홍"); p.setBirth(LocalDate.now()); p.setGender("M");
            when(patientRepository.findById(eq(2))).thenReturn(Optional.of(p));
            when(historyRepository.searchHistories(eq(2), any(LocalDateTime.class), any(LocalDateTime.class)))
                    .thenReturn(Collections.emptyList());
            var res = historyService.searchHistory(2, new Date(), new Date());
            assertThat(res).containsKeys("patientId", "histories");
        }
    }
}
