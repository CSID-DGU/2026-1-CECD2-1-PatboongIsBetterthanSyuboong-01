package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.PatientRepository;
import com.example.bitcomputer.entity.Patient;
import com.example.bitcomputer.model.PatientDTO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.Date;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class PatientServiceImplTest {

    @Mock
    PatientRepository patientRepository;

    @InjectMocks
    PatientServiceImpl patientService;

    @BeforeEach
    void setUp() { MockitoAnnotations.openMocks(this); }

    private PatientDTO valid() {
        PatientDTO d = new PatientDTO();
        d.setName("n"); d.setPhoneNumber("010"); d.setIdentityNumber("900101-1234567");
        d.setBirth(new Date()); d.setGender("M");
        return d;
    }

    @Nested
    @DisplayName("createPatient")
    class Create {
        @Test
        @DisplayName("중복 ID면 409")
        void duplicate_identity() {
            when(patientRepository.existsById(eq(1))).thenReturn(true);
            PatientDTO d = valid();
            d.setId(1);
            assertThatThrownBy(() -> patientService.createPatient(d))
                    .isInstanceOf(ResponseStatusException.class)
                    .extracting("statusCode")
                    .asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.type(HttpStatus.class))
                    .isEqualTo(HttpStatus.CONFLICT);
        }

        @Test
        @DisplayName("유효성 오류면 400")
        void validation_error() {
            PatientDTO d = new PatientDTO();
            assertThatThrownBy(() -> patientService.createPatient(d))
                    .isInstanceOf(ResponseStatusException.class)
                    .extracting("statusCode")
                    .asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.type(HttpStatus.class))
                    .isEqualTo(HttpStatus.BAD_REQUEST);
        }

        @Test
        @DisplayName("정상 생성 시 저장/매핑 확인")
        void create_success() {
            when(patientRepository.existsById(anyInt())).thenReturn(false);
            Patient saved = new Patient();
            saved.setId(10);
            when(patientRepository.save(any(Patient.class))).thenReturn(saved);
            PatientDTO res = patientService.createPatient(valid());
            assertThat(res.getId()).isEqualTo(10);
        }
    }

    @Nested
    @DisplayName("searchPatientById")
    class SearchById {
        @Test
        @DisplayName("존재하지 않으면 404")
        void not_found() {
            when(patientRepository.findById(eq(99))).thenReturn(java.util.Optional.empty());
            assertThatThrownBy(() -> patientService.searchPatientById(99))
                    .isInstanceOf(ResponseStatusException.class)
                    .extracting("statusCode")
                    .asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.type(HttpStatus.class))
                    .isEqualTo(HttpStatus.NOT_FOUND);
        }

        @Test
        @DisplayName("존재하면 DTO 반환")
        void success() {
            Patient p = new Patient(); p.setId(5); p.setName("n");
            when(patientRepository.findById(eq(5))).thenReturn(java.util.Optional.of(p));
            PatientDTO res = patientService.searchPatientById(5);
            assertThat(res.getId()).isEqualTo(5);
        }
    }
}
