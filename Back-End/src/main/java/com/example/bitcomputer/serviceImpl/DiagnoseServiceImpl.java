package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.DiagnoseRepository;
import com.example.bitcomputer.entity.Diagnose;
import com.example.bitcomputer.model.DiagnoseDTO;
import com.example.bitcomputer.model.PaginatedResponse;
import com.example.bitcomputer.service.DiagnoseService;
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
public class DiagnoseServiceImpl implements DiagnoseService {

    private final DiagnoseRepository diagnoseRepository;

    public DiagnoseServiceImpl(DiagnoseRepository diagnoseRepository) {
        this.diagnoseRepository = diagnoseRepository;
    }

    @Override
    public DiagnoseDTO getById(int id) {
        Diagnose entity = diagnoseRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Diagnose not found with id " + id));
        return toDto(entity);
    }

    @Override
    public PaginatedResponse<DiagnoseDTO> search(String query, String code, String name, int page, int size) {
        String codeQuery = resolveSearchValue(query, code);
        String nameQuery = resolveSearchValue(query, name);

        Pageable pageable = PageRequest.of(
                Math.max(page, 0),
                normalizeSize(size),
                Sort.by("name").ascending()
        );

        Page<Diagnose> result = diagnoseRepository
                .findByCodeContainingIgnoreCaseOrNameContainingIgnoreCase(codeQuery, nameQuery, pageable);

        List<DiagnoseDTO> items = result.getContent()
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

        List<Diagnose> diagnoses = new ArrayList<>();
        
        try (FileInputStream fis = new FileInputStream(file);
        Workbook workbook = new XSSFWorkbook(fis)) {
            Sheet sheet = workbook.getSheetAt(0);
            
            for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                Row row = sheet.getRow(i);
                if (row == null) continue;
                
                Cell codeCell = row.getCell(0);
                Cell nameCell = row.getCell(1);
                // 처방 데이터 불규칙성으로 인해 2번째 열까지만 받아옴
                // dose, time, days 저장하지 않음 (2열에 포함되어 있음)

                // Cell doseCell = row.getCell(2);
                // Cell timeCell = row.getCell(3);
                // Cell daysCell = row.getCell(4);

                if (codeCell == null || nameCell == null) continue;
                
                String code = getCellValueAsString(codeCell);
                String name = getCellValueAsString(nameCell);
                // int dose = getCellValueAsInt(doseCell);
                // int time = getCellValueAsInt(timeCell);
                // int days = getCellValueAsInt(daysCell);
                
                if (code == null || code.trim().isEmpty() || 
                    name == null || name.trim().isEmpty()) {
                    continue;
                }
                
                // 이미 존재하는지 확인
                Diagnose existingDiagnoseCode = diagnoseRepository.findByCode(code).orElse(null);
                Diagnose existingDiagnoseName = diagnoseRepository.findByName(name).orElse(null);

                if (existingDiagnoseCode == null || existingDiagnoseName == null) {
                    Diagnose diagnose = new Diagnose();
                    diagnose.setCode(code.trim());
                    diagnose.setName(name.trim());
                    // dose, time, days는 nullable=false이므로 기본값 0으로 설정
                    diagnose.setDose(0);
                    diagnose.setTime(0);
                    diagnose.setDays(0);
                    diagnoses.add(diagnose);
                }
            }
            
            diagnoseRepository.saveAll(diagnoses);
            return diagnoses.size();
            
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
    
    private int getCellValueAsInt(Cell cell) {
        if (cell == null) return 0;
        
        switch (cell.getCellType()) {
            case NUMERIC:
                return (int) cell.getNumericCellValue();
            case STRING:
                try {
                    return Integer.parseInt(cell.getStringCellValue().trim());
                } catch (NumberFormatException e) {
                    return 0;
                }
            default:
                return 0;
        }
    }

    private DiagnoseDTO toDto(Diagnose entity) {
        DiagnoseDTO dto = new DiagnoseDTO();
        dto.setId(entity.getId());
        dto.setCode(entity.getCode());
        dto.setName(entity.getName());
        dto.setDose(entity.getDose());
        dto.setTime(entity.getTime());
        dto.setDays(entity.getDays());
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

