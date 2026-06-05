package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.DiseaseRepository;
import com.example.bitcomputer.entity.Disease;
import com.example.bitcomputer.model.DiseaseDTO;
import com.example.bitcomputer.model.PaginatedResponse;
import com.example.bitcomputer.service.DiseaseService;
import jakarta.persistence.EntityNotFoundException;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class DiseaseServiceImpl implements DiseaseService {

    private final DiseaseRepository diseaseRepository;

    public DiseaseServiceImpl(DiseaseRepository diseaseRepository) {
        this.diseaseRepository = diseaseRepository;
    }

    @Override
    public DiseaseDTO getById(int id) {
        Disease entity = diseaseRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Disease not found with id " + id));
        return toDto(entity);
    }

    @Override
    public PaginatedResponse<DiseaseDTO> search(String query, String code, String name, int page, int size) {
        String codeQuery = resolveSearchValue(query, code);
        String nameQuery = resolveSearchValue(query, name);

        Pageable pageable = PageRequest.of(
                Math.max(page, 0),
                normalizeSize(size),
                Sort.by("name").ascending()
        );

        Page<Disease> result = diseaseRepository
                .searchByCodeOrNameOrNameEn(codeQuery, nameQuery, pageable);

        List<DiseaseDTO> items = result.getContent()
                .stream()
                .map(this::toDto)
                .collect(Collectors.toList());

        return new PaginatedResponse<>(items, result.getTotalElements(), result.getNumber(), result.getSize());
    }

    @Override
    public int uploadFromExcel(File file) {
        if (file == null || !file.exists()) {
            throw new IllegalArgumentException("파일이 존재하지 않습니다: " + (file != null ? file.getPath() : "null"));
        }

        if (!file.getName().endsWith(".xlsx") && !file.getName().endsWith(".xls")) {
            throw new IllegalArgumentException("엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.");
        }

        List<Disease> diseases = new ArrayList<>();
        
        try (FileInputStream fis = new FileInputStream(file);
        Workbook workbook = new XSSFWorkbook(fis)) {
            Sheet sheet = workbook.getSheetAt(0);
            
            // 첫 번째 행은 헤더로 간주하고 건너뜀
            for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                Row row = sheet.getRow(i);
                if (row == null) continue;
                
                // code 컬럼 (0번 인덱스)
                Cell codeCell = row.getCell(0);
                // name 컬럼 (1번 인덱스), 상병명(영문) (2번 인덱스, 선택)
                Cell nameCell = row.getCell(1);
                Cell nameEnCell = row.getCell(2);

                if (codeCell == null || nameCell == null) continue;

                String code = getCellValueAsString(codeCell);
                String name = getCellValueAsString(nameCell);
                String nameEn = nameEnCell != null ? getCellValueAsString(nameEnCell) : null;

                if (code == null || code.trim().isEmpty() ||
                    name == null || name.trim().isEmpty()) {
                    continue;
                }
                
                // 이미 존재하는지 확인
                Disease existingDiseaseCode = diseaseRepository.findByCode(code).orElse(null);
                Disease existingDiseaseName = diseaseRepository.findByName(name).orElse(null);

                if (existingDiseaseCode == null || existingDiseaseName == null) {
                    Disease disease = new Disease();
                    disease.setCode(code.trim());
                    disease.setName(name.trim());
                    if (nameEn != null && !nameEn.trim().isEmpty()) {
                        disease.setNameEn(nameEn.trim());
                    }
                    diseases.add(disease);
                }
            }
            
            diseaseRepository.saveAll(diseases);
            return diseases.size();
            
        } catch (IOException e) {
            throw new RuntimeException("엑셀 파일을 읽는 중 오류가 발생했습니다: " + e.getMessage(), e);
        }
    }
    
    private String getCellValueAsString(Cell cell) {
        if (cell == null) return null;
        
        switch (cell.getCellType()) {
            case STRING:
                return cell.getStringCellValue();
            case NUMERIC:
                if (DateUtil.isCellDateFormatted(cell)) {
                    return cell.getDateCellValue().toString();
                } else {
                    double numericValue = cell.getNumericCellValue();
                    if (numericValue == (long) numericValue) {
                        return String.valueOf((long) numericValue);
                    } else {
                        return String.valueOf(numericValue);
                    }
                }
            case BOOLEAN:
                return String.valueOf(cell.getBooleanCellValue());
            case FORMULA:
                return cell.getCellFormula();
            default:
                return null;
        }
    }

    private DiseaseDTO toDto(Disease entity) {
        DiseaseDTO dto = new DiseaseDTO();
        dto.setId(entity.getId());
        dto.setCode(entity.getCode());
        dto.setName(entity.getName());
        dto.setNameEn(entity.getNameEn());
        return dto;
    }

    private String resolveSearchValue(String primary, String fallback) {
        if (primary != null && !primary.isBlank()) {
            return primary.trim();
        }
        return fallback != null ? fallback.trim() : "";
    }

    private int normalizeSize(int size) {
        int defaultSize = 50;
        if (size <= 0) {
            return defaultSize;
        }
        return Math.min(size, 200);
    }
}

