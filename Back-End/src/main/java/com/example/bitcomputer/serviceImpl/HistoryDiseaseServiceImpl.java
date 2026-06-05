package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryDiseaseRepository;
import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.DiseaseRepository;
import com.example.bitcomputer.entity.Disease;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.HistoryDisease;
import com.example.bitcomputer.model.HistoryDiseaseDTO;
import com.example.bitcomputer.service.HistoryDiseaseService;
import jakarta.persistence.EntityNotFoundException;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class HistoryDiseaseServiceImpl implements HistoryDiseaseService {

    private final HistoryDiseaseRepository historyDiseaseRepository;
    private final HistoryRepository historyRepository;
    private final DiseaseRepository diseaseRepository;

    public HistoryDiseaseServiceImpl(
            HistoryDiseaseRepository historyDiseaseRepository,
            HistoryRepository historyRepository,
            DiseaseRepository diseaseRepository) {
        this.historyDiseaseRepository = historyDiseaseRepository;
        this.historyRepository = historyRepository;
        this.diseaseRepository = diseaseRepository;
    }

    @Override
    @Transactional
    public List<HistoryDiseaseDTO> setDiseasesForHistory(int employeeId, int historyId, List<HistoryDiseaseDTO> diseases) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        historyDiseaseRepository.deleteByHistoryId(history.getId());

        List<HistoryDisease> toSave = diseases.stream()
                .map(dto -> {
                    HistoryDisease entity = new HistoryDisease();
                    entity.setHistoryId(history.getId());
                    entity.setDegree(dto.getDegree());

                    String code = dto.getCode();
                    if (code == null || code.isBlank()) {
                        throw new IllegalArgumentException("Disease code must not be null or blank");
                    }
                    entity.setCode(code);

                    String name = dto.getName();
                    if (name == null || name.isBlank()) {
                        name = diseaseRepository.findByCode(code)
                                .orElseThrow(() -> new EntityNotFoundException("Disease Name not found with code " + code))
                                .getName();
                    }
                    entity.setName(name);

                    return entity;
                })
                .collect(Collectors.toList());

        List<HistoryDisease> saved = historyDiseaseRepository.saveAll(toSave);
        history.setSymptomDetail(formatDiseasesForHistory(saved));

        return saved.stream().map(this::toDto).collect(Collectors.toList());
    }

    @Override
    @Transactional
    public HistoryDiseaseDTO addDiseaseById(int employeeId, int historyId, int diseaseId, String degree) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        Disease disease = diseaseRepository.findById(diseaseId)
                .orElseThrow(() -> new EntityNotFoundException("Disease not found with id " + diseaseId));

        List<HistoryDisease> existing = historyDiseaseRepository.findByHistoryId(historyId);
        boolean alreadyExists = existing.stream()
                .anyMatch(hd -> hd.getCode().equals(disease.getCode()));
        
        if (alreadyExists) {
            throw new IllegalArgumentException("Disease already exists for this history");
        }

        HistoryDisease entity = new HistoryDisease();
        entity.setHistoryId(history.getId());
        entity.setCode(disease.getCode());
        entity.setName(disease.getName());
        entity.setDegree(degree);

        HistoryDisease saved = historyDiseaseRepository.save(entity);
        List<HistoryDisease> currentDiseases = historyDiseaseRepository.findByHistoryId(historyId);
        history.setSymptomDetail(formatDiseasesForHistory(currentDiseases));

        return toDto(saved);
    }

    @Override
    @Transactional
    public List<HistoryDiseaseDTO> getDiseasesForHistory(int employeeId, int historyId) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found with id " + historyId));

        if (history.getEmployeeId() != employeeId) {
            throw new org.springframework.security.access.AccessDeniedException("Forbidden");
        }

        return historyDiseaseRepository.findByHistoryId(historyId)
                .stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    private HistoryDiseaseDTO toDto(HistoryDisease entity) {
        HistoryDiseaseDTO dto = new HistoryDiseaseDTO();
        dto.setId(entity.getId());
        dto.setHistoryId(entity.getHistoryId());
        dto.setDegree(entity.getDegree());
        dto.setCode(entity.getCode());
        dto.setName(entity.getName());
        return dto;
    }

    private String formatDiseasesForHistory(List<HistoryDisease> diseases) {
        if (diseases == null || diseases.isEmpty()) {
            return "";
        }
        return diseases.stream()
                .map(disease -> {
                    String code = disease.getCode() != null ? disease.getCode().trim() : "";
                    String name = disease.getName() != null ? disease.getName().trim() : "";
                    if (code.isBlank()) {
                        return name;
                    }
                    if (name.isBlank()) {
                        return code;
                    }
                    return code + " " + name;
                })
                .filter(value -> value != null && !value.isBlank())
                .collect(Collectors.joining(", "));
    }
}