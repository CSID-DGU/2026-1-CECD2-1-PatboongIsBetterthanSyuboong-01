package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.PatientRepository;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.Patient;
import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.model.PatientDTO;
import com.example.bitcomputer.model.WriteHistoryDTO;
import com.example.bitcomputer.service.HistoryService;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

import jakarta.persistence.EntityNotFoundException;

@Service
public class HistoryServiceImpl implements HistoryService {

    private final HistoryRepository historyRepository;
    private final PatientRepository patientRepository;

    public HistoryServiceImpl(HistoryRepository historyRepository, PatientRepository patientRepository) {
        this.historyRepository = historyRepository;
        this.patientRepository = patientRepository;
    }

    @Override
    public HistoryDTO writeHistory(HistoryDTO request) {
        History history = mapToEntity(request);
        History saved = historyRepository.save(history);
        return mapToDto(saved);
    }

    @Override
    public HistoryDTO updateHistory(int id, HistoryDTO request) {
        History history = historyRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + id));

        if (request.getEmployeeId() != null) {
            history.setEmployeeId(request.getEmployeeId());
        }
        if (request.getPatientId() != null) {
            history.setPatientId(request.getPatientId());
        }
        if (request.getDeptId() != null) {
            history.setDeptId(request.getDeptId());
        }
        if (request.getSymptomDetail() != null) {
            history.setSymptomDetail(request.getSymptomDetail());
        }
        if (request.getMemo() != null) {
            history.setMemo(request.getMemo());
        }
        if (request.getEntryDate() != null) {
            history.setEntryDate(convertToLocalDateTime(request.getEntryDate()));
        }

        History saved = historyRepository.save(history);
        return mapToDto(saved);
    }

    private History mapToEntity(HistoryDTO dto) {
        History history = new History();
        history.setEmployeeId(Objects.requireNonNull(dto.getEmployeeId(), "employeeId must not be null"));
        history.setPatientId(Objects.requireNonNull(dto.getPatientId(), "patientId must not be null"));
        history.setDeptId(Objects.requireNonNull(dto.getDeptId(), "deptId must not be null"));
        history.setSymptomDetail(dto.getSymptomDetail());
        history.setMemo(dto.getMemo());
        history.setEntryDate(convertToLocalDateTime(dto.getEntryDate()));
        return history;
    }

    private HistoryDTO mapToDto(History history) {
        HistoryDTO dto = new HistoryDTO();
        dto.setId(history.getId());
        dto.setEmployeeId(history.getEmployeeId());
        dto.setPatientId(history.getPatientId());
        dto.setDeptId(history.getDeptId());
        dto.setSymptomDetail(history.getSymptomDetail());
        dto.setMemo(history.getMemo());

        LocalDateTime entryDate = history.getEntryDate();
        dto.setEntryDate(convertToDate(entryDate));

        return dto;
    }

    //Description: 로그인한 직원이 조건에 따라 환자의 진료 기록을 검색. 검색 성공 시, 조건에 맞는 진료 기록 목록을 반환.
    @Override
    public Map<String, Object> searchHistory(int patientId, Date startDate, Date endDate) {
        Patient patient = patientRepository.findById(patientId)
                .orElseThrow(() -> new EntityNotFoundException("Patient not found with id " + patientId));

        LocalDateTime start = convertToStartOfDay(startDate);
        LocalDateTime end = convertToEndOfDay(endDate);
        List<History> histories = historyRepository.searchHistories(patientId, start, end);

        java.util.Map<String, Object> result = new java.util.HashMap<>();
        result.put("patientId", patient.getId());
        result.put("histories", histories.stream()
                .map(this::mapToDto)
                .collect(Collectors.toList()));
        return result;
    }   

    @Override
    public HistoryDTO writeHistory(WriteHistoryDTO request) {
        History history = new History();
        history.setEmployeeId(request.getEmployeeId());
        history.setPatientId(request.getPatientId());
        history.setDeptId(request.getDeptId());
        history.setSymptomDetail(request.getSymptomDetail());
        history.setMemo(request.getMemo());
        history.setEntryDate(convertToLocalDateTime(request.getEntryDate()));

        return mapToDto(historyRepository.save(history));
    }

    @Override
    public HistoryDTO updateHistory(int id, WriteHistoryDTO request) {
        History history = historyRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + id));
        history.setEmployeeId(request.getEmployeeId());
        history.setPatientId(request.getPatientId());
        history.setDeptId(request.getDeptId());
        history.setSymptomDetail(request.getSymptomDetail());
        history.setMemo(request.getMemo());
        history.setEntryDate(convertToLocalDateTime(request.getEntryDate()));
        return mapToDto(historyRepository.save(history));
    }

    private LocalDateTime convertToLocalDateTime(Date entryDate) {
        if (entryDate == null) {
            return LocalDateTime.now();
        }

        return LocalDateTime.ofInstant(entryDate.toInstant(), ZoneId.systemDefault());
    }

    private Date convertToDate(LocalDateTime entryDate) {
        if (entryDate == null) {
            return null;
        }

        return Date.from(entryDate.atZone(ZoneId.systemDefault()).toInstant());
    }

    private PatientDTO mapPatientToDto(Patient patient) {
        PatientDTO dto = new PatientDTO();
        dto.setId(patient.getId());
        dto.setName(patient.getName());
        dto.setPhoneNumber(patient.getPhoneNumber());
        dto.setIdentityNumber(patient.getIdentityNumber());
        dto.setBirth(convertToDate(patient.getBirth()));
        dto.setGender(patient.getGender());
        return dto;
    }

    private Date convertToDate(LocalDate localDate) {
        if (localDate == null) {
            return null;
        }

        return Date.from(localDate.atStartOfDay(ZoneId.systemDefault()).toInstant());
    }

    private LocalDateTime convertToStartOfDay(Date date) {
        if (date == null) {
            return null;
        }

        return LocalDateTime.ofInstant(date.toInstant(), ZoneId.systemDefault()).with(LocalTime.MIN);
    }

    private LocalDateTime convertToEndOfDay(Date date) {
        if (date == null) {
            return null;
        }

        return LocalDateTime.ofInstant(date.toInstant(), ZoneId.systemDefault()).with(LocalTime.MAX);
    }
}

