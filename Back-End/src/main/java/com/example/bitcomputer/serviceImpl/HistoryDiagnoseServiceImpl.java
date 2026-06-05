package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryDiagnoseRepository;
import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.DiagnoseRepository;
import com.example.bitcomputer.entity.Diagnose;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.HistoryDiagnose;
import com.example.bitcomputer.model.HistoryDiagnoseDTO;
import com.example.bitcomputer.service.HistoryDiagnoseService;
import jakarta.persistence.EntityNotFoundException;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class HistoryDiagnoseServiceImpl implements HistoryDiagnoseService {

    private final HistoryDiagnoseRepository historyDiagnoseRepository;
    private final HistoryRepository historyRepository;
    private final DiagnoseRepository diagnoseRepository;

    public HistoryDiagnoseServiceImpl(
            HistoryDiagnoseRepository historyDiagnoseRepository,
            HistoryRepository historyRepository,
            DiagnoseRepository diagnoseRepository) {
        this.historyDiagnoseRepository = historyDiagnoseRepository;
        this.historyRepository = historyRepository;
        this.diagnoseRepository = diagnoseRepository;
    }

    @Override
    @Transactional
    public List<HistoryDiagnoseDTO> setDiagnosesForHistory(int employeeId, int historyId, List<HistoryDiagnoseDTO> diagnoses) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        historyDiagnoseRepository.deleteByHistoryId(history.getId());

        List<HistoryDiagnose> toSave = diagnoses.stream()
                .map(dto -> {
                    HistoryDiagnose entity = new HistoryDiagnose();
                    entity.setHistoryId(history.getId());

                    int diagnoseId = dto.getId();
                    if (diagnoseId <= 0) {
                        throw new IllegalArgumentException("Diagnose id must be valid");
                    }

                    Diagnose diagnose = diagnoseRepository.findById(diagnoseId)
                            .orElseThrow(() -> new EntityNotFoundException("Diagnose not found with id " + diagnoseId));

                    entity.setCode(diagnose.getCode());
                    entity.setName(diagnose.getName());
                    entity.setDose(diagnose.getDose());
                    entity.setTime(diagnose.getTime());
                    entity.setDays(diagnose.getDays());

                    return entity;
                })
                .collect(Collectors.toList());

        List<HistoryDiagnose> saved = historyDiagnoseRepository.saveAll(toSave);
        history.setEntryDate(LocalDateTime.now());
        historyRepository.save(history);
        return saved.stream().map(this::toDto).collect(Collectors.toList());
    }

    @Override
    @Transactional
    public HistoryDiagnoseDTO addDiagnoseById(int employeeId, int historyId, int diagnoseId) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        Diagnose diagnose = diagnoseRepository.findById(diagnoseId)
                .orElseThrow(() -> new EntityNotFoundException("Diagnose not found with id " + diagnoseId));

        List<HistoryDiagnose> existing = historyDiagnoseRepository.findByHistoryId(historyId);
        boolean alreadyExists = existing.stream()
                .anyMatch(hd -> hd.getCode().equals(diagnose.getCode()));

        if (alreadyExists) {
            throw new IllegalArgumentException("Diagnose already exists for this history");
        }

        HistoryDiagnose entity = new HistoryDiagnose();
        entity.setHistoryId(history.getId());
        entity.setCode(diagnose.getCode());
        entity.setName(diagnose.getName());
        entity.setDose(diagnose.getDose());
        entity.setTime(diagnose.getTime());
        entity.setDays(diagnose.getDays());

        HistoryDiagnose saved = historyDiagnoseRepository.save(entity);
        history.setEntryDate(LocalDateTime.now());
        historyRepository.save(history);
        return toDto(saved);
    }

    @Override
    @Transactional
    public List<HistoryDiagnoseDTO> getDiagnosesForHistory(int employeeId, int historyId) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        return historyDiagnoseRepository.findByHistoryId(historyId)
                .stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    private HistoryDiagnoseDTO toDto(HistoryDiagnose entity) {
        HistoryDiagnoseDTO dto = new HistoryDiagnoseDTO();
        dto.setId(entity.getId());
        dto.setHistoryId(entity.getHistoryId());
        dto.setCode(entity.getCode());
        dto.setName(entity.getName());
        dto.setDose(entity.getDose());
        dto.setTime(entity.getTime());
        dto.setDays(entity.getDays());
        return dto;
    }
}

