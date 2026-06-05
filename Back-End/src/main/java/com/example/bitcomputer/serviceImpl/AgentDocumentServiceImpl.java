package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.*;
import com.example.bitcomputer.entity.*;
import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.model.CertificateAgentRequest;
import com.example.bitcomputer.model.CertificateFormDTO;
import com.example.bitcomputer.model.CertificateHistoryDTO;
import com.example.bitcomputer.model.GenerateCertificateResponseDTO;
import com.example.bitcomputer.model.PastPrescriptionDTO;
import com.example.bitcomputer.service.AgentDocumentService;
import jakarta.persistence.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.Period;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
public class AgentDocumentServiceImpl implements AgentDocumentService {

    private final HistoryRepository historyRepository;
    private final PatientRepository patientRepository;
    private final EmployeeRepository employeeRepository;
    private final DeptRepository deptRepository;
    private final HistoryDiseaseRepository historyDiseaseRepository;
    private final HistoryDiagnoseRepository historyDiagnoseRepository;
    private final MedicalCertificateRepository medicalCertificateRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final CertificateAgentClient certificateAgentClient;

    @Value("${medical.certificate.storage-path:certificates}")
    private String certificateStoragePath;

    public AgentDocumentServiceImpl(
            HistoryRepository historyRepository,
            PatientRepository patientRepository,
            EmployeeRepository employeeRepository,
            DeptRepository deptRepository,
            HistoryDiseaseRepository historyDiseaseRepository,
            HistoryDiagnoseRepository historyDiagnoseRepository,
            MedicalCertificateRepository medicalCertificateRepository,
            JwtTokenProvider jwtTokenProvider,
            CertificateAgentClient certificateAgentClient) {
        this.historyRepository = historyRepository;
        this.patientRepository = patientRepository;
        this.employeeRepository = employeeRepository;
        this.deptRepository = deptRepository;
        this.historyDiseaseRepository = historyDiseaseRepository;
        this.historyDiagnoseRepository = historyDiagnoseRepository;
        this.medicalCertificateRepository = medicalCertificateRepository;
        this.jwtTokenProvider = jwtTokenProvider;
        this.certificateAgentClient = certificateAgentClient;
    }

    @Override
    public CertificateFormDTO getHistoryDetail(Integer historyId) {
        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found: " + historyId));

        Patient patient = patientRepository.findById(history.getPatientId())
                .orElseThrow(() -> new EntityNotFoundException("Patient not found: " + history.getPatientId()));

        CertificateFormDTO dto = new CertificateFormDTO();
        dto.setHistoryId(historyId);
        dto.setPatientName(patient.getName());
        dto.setPatientNumber(String.valueOf(patient.getId()));
        dto.setAge(calculateAge(patient.getBirth()));
        dto.setGender(patient.getGender());
        dto.setEntryDate(history.getEntryDate().toLocalDate().format(DateTimeFormatter.ISO_LOCAL_DATE));
        dto.setSymptomDetail(history.getSymptomDetail());

        employeeRepository.findById(history.getEmployeeId())
                .ifPresent(e -> dto.setDoctor(e.getName()));

        deptRepository.findById(history.getDeptId()).ifPresent(d -> dto.setDepartment(d.getDept()));

        dto.setDiseases(historyDiseaseRepository.findByHistoryId(historyId).stream().map(d -> {
            CertificateFormDTO.DiseaseInfo info = new CertificateFormDTO.DiseaseInfo();
            info.setCode(d.getCode());
            info.setName(d.getName());
            info.setDegree(d.getDegree());
            return info;
        }).collect(Collectors.toList()));

        dto.setDiagnoses(historyDiagnoseRepository.findByHistoryId(historyId).stream().map(d -> {
            CertificateFormDTO.DiagnoseInfo info = new CertificateFormDTO.DiagnoseInfo();
            info.setCode(d.getCode());
            info.setName(d.getName());
            info.setDose(d.getDose());
            info.setTime(d.getTime());
            info.setDays(d.getDays());
            return info;
        }).collect(Collectors.toList()));

        return dto;
    }

    @Override
    public List<PastPrescriptionDTO> getPastPrescriptions(Integer historyId) {
        History current = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found: " + historyId));

        List<History> pastHistories = historyRepository
                .searchHistories(current.getPatientId(), null, null)
                .stream()
                .filter(h -> h.getId() != historyId)
                .collect(Collectors.toList());

        if (pastHistories.isEmpty()) return Collections.emptyList();

        List<Integer> pastHistoryIds = pastHistories.stream()
                .map(History::getId)
                .collect(Collectors.toList());

        Map<Integer, List<HistoryDiagnose>> diagnosesByHistory =
                historyDiagnoseRepository.findByHistoryIdIn(pastHistoryIds)
                        .stream()
                        .collect(Collectors.groupingBy(HistoryDiagnose::getHistoryId));

        return pastHistories.stream()
                .map(h -> {
                    PastPrescriptionDTO dto = new PastPrescriptionDTO();
                    dto.setHistoryId(h.getId());
                    dto.setEntryDate(h.getEntryDate().toLocalDate().format(DateTimeFormatter.ISO_LOCAL_DATE));
                    List<PastPrescriptionDTO.DiagnoseInfo> infos = diagnosesByHistory
                            .getOrDefault(h.getId(), Collections.emptyList())
                            .stream()
                            .map(d -> {
                                PastPrescriptionDTO.DiagnoseInfo info = new PastPrescriptionDTO.DiagnoseInfo();
                                info.setCode(d.getCode());
                                info.setName(d.getName());
                                info.setDose(d.getDose());
                                info.setTime(d.getTime());
                                info.setDays(d.getDays());
                                return info;
                            }).collect(Collectors.toList());
                    dto.setDiagnoses(infos);
                    return dto;
                })
                .collect(Collectors.toList());
    }

    @Override
    public List<CertificateHistoryDTO> searchCertificates(
            String patientName, String patientNumber, String department,
            String doctorName, String startDate, String endDate) {

        LocalDateTime start = parseStartDateTime(startDate);
        LocalDateTime end = parseEndDateTime(endDate);

        // 1. 날짜 범위 기반 전체 조회
        List<History> histories = historyRepository.searchAllHistories(start, end);

        // 2. 환자 필터 (환자명 또는 환자번호)
        boolean hasPatientFilter = isNotBlank(patientName) || isNotBlank(patientNumber);
        if (hasPatientFilter) {
            Set<Integer> matchedPatientIds = new HashSet<>();

            if (isNotBlank(patientName)) {
                patientRepository.findByNameContainingIgnoreCase(patientName)
                        .forEach(p -> matchedPatientIds.add(p.getId()));
            }
            if (isNotBlank(patientNumber)) {
                // 숫자이면 patient.id로 검색, 아니면 identityNumber로 검색
                try {
                    int pid = Integer.parseInt(patientNumber.trim());
                    patientRepository.findById(pid).ifPresent(p -> matchedPatientIds.add(p.getId()));
                } catch (NumberFormatException e) {
                    Patient p = patientRepository.findByIdentityNumber(patientNumber.trim());
                    if (p != null) matchedPatientIds.add(p.getId());
                }
            }

            if (matchedPatientIds.isEmpty()) return Collections.emptyList();
            histories = histories.stream()
                    .filter(h -> matchedPatientIds.contains(h.getPatientId()))
                    .collect(Collectors.toList());
        }

        // 3. 진료과 필터
        if (isNotBlank(department)) {
            Set<Integer> deptIds = deptRepository.findByDeptContainingIgnoreCase(department)
                    .stream().map(Dept::getId).collect(Collectors.toSet());
            if (deptIds.isEmpty()) return Collections.emptyList();
            histories = histories.stream()
                    .filter(h -> deptIds.contains(h.getDeptId()))
                    .collect(Collectors.toList());
        }

        // 4. 진료의 필터
        if (isNotBlank(doctorName)) {
            Set<Integer> empIds = employeeRepository.findByNameContainingIgnoreCase(doctorName)
                    .stream().map(Employee::getId).collect(Collectors.toSet());
            if (empIds.isEmpty()) return Collections.emptyList();
            histories = histories.stream()
                    .filter(h -> empIds.contains(h.getEmployeeId()))
                    .collect(Collectors.toList());
        }

        if (histories.isEmpty()) return Collections.emptyList();

        // 5. 전체 조회
        List<Integer> historyIds = histories.stream().map(History::getId).collect(Collectors.toList());
        List<Integer> patientIds = histories.stream().map(History::getPatientId).distinct().collect(Collectors.toList());
        List<Integer> employeeIds = histories.stream().map(History::getEmployeeId).distinct().collect(Collectors.toList());
        List<Integer> deptIds2 = histories.stream().map(History::getDeptId).distinct().collect(Collectors.toList());

        Map<Integer, Patient> patientMap = patientRepository.findAllById(patientIds).stream()
                .collect(Collectors.toMap(Patient::getId, p -> p));
        Map<Integer, Employee> employeeMap = employeeRepository.findAllById(employeeIds).stream()
                .collect(Collectors.toMap(Employee::getId, e -> e));
        Map<Integer, Dept> deptMap2 = deptRepository.findAllById(deptIds2).stream()
                .collect(Collectors.toMap(Dept::getId, d -> d));
        Map<Integer, String> issueDateMap = medicalCertificateRepository.findByHistoryIdIn(historyIds)
                .stream()
                .collect(Collectors.groupingBy(
                        MedicalCertificateRecord::getHistoryId,
                        Collectors.collectingAndThen(
                                Collectors.maxBy(Comparator.comparing(MedicalCertificateRecord::getCreatedAt)),
                                opt -> opt.map(r -> r.getCreatedAt().toLocalDate()
                                        .format(DateTimeFormatter.ISO_LOCAL_DATE)).orElse(null)
                        )
                ));

        return histories.stream().map(h -> {
            CertificateHistoryDTO dto = new CertificateHistoryDTO();
            dto.setHistoryId(h.getId());
            dto.setPatientId(h.getPatientId());
            dto.setSymptomDetail(h.getSymptomDetail());
            dto.setIssueDate(issueDateMap.get(h.getId()));

            Patient p = patientMap.get(h.getPatientId());
            if (p != null) {
                dto.setPatientName(p.getName());
                dto.setPatientNumber(String.valueOf(p.getId()));
                dto.setGender(p.getGender());
                dto.setAge(calculateAge(p.getBirth()));
            }
            Employee e = employeeMap.get(h.getEmployeeId());
            if (e != null) dto.setDoctor(e.getName());

            Dept d = deptMap2.get(h.getDeptId());
            if (d != null) dto.setDepartment(d.getDept());

            return dto;
        }).collect(Collectors.toList());
    }

    private boolean isNotBlank(String s) {
        return s != null && !s.isBlank();
    }

    @Override
    public GenerateCertificateResponseDTO generateCertificate(
            Integer historyId,
            String certificateType,
            String diagnosisKind,
            String purpose,
            String username) {

        History history = historyRepository.findById(historyId)
                .orElseThrow(() -> new EntityNotFoundException("History not found: " + historyId));

        Patient patient = patientRepository.findById(history.getPatientId())
                .orElseThrow(() -> new EntityNotFoundException("Patient not found: " + history.getPatientId()));

        List<HistoryDisease> diseases = historyDiseaseRepository.findByHistoryId(historyId);
        List<HistoryDiagnose> diagnoses = historyDiagnoseRepository.findByHistoryId(historyId);

        // Python 진단서 에이전트 요청 DTO 구성
        CertificateAgentRequest agentRequest = CertificateAgentRequest.builder()
                .historyId(historyId)
                .certificateType(normalizeCertificateType(certificateType))
                .patientName(patient.getName())
                .patientAge(calculateAge(patient.getBirth()))
                .patientGender(patient.getGender())
                .entryDate(history.getEntryDate().toLocalDate().toString())
                .symptomDetail(history.getSymptomDetail())
                .diagnosisKind(normalizeDiagnosisKind(diagnosisKind))
                .purpose(normalizePurpose(purpose))
                .diseases(diseases.stream().map(d -> CertificateAgentRequest.DiseaseInfo.builder()
                        .code(d.getCode())
                        .name(d.getName())
                        .degree(d.getDegree())
                        .build()).collect(Collectors.toList()))
                .diagnoses(diagnoses.stream().map(d -> CertificateAgentRequest.DiagnoseInfo.builder()
                        .code(d.getCode())
                        .name(d.getName())
                        .dose(d.getDose())
                        .time(d.getTime())
                        .days(d.getDays())
                        .build()).collect(Collectors.toList()))
                .build();

        // Python 진단서 에이전트 호출 → 실패 시 기본 템플릿으로 폴백
        String medicalCertificate = certificateAgentClient.generate(agentRequest)
                .map(r -> r.getMedicalCertificate())
                .filter(s -> s != null && !s.isBlank())
                .orElseGet(() -> buildDefaultCertificateTemplate(agentRequest));

        return buildGenerateResponse(username, medicalCertificate);
    }

    @Override
    public GenerateCertificateResponseDTO generateTestCertificate(
            String diseaseCode,
            String prescriptionCode,
            String prescriptionName,
            String certificateType,
            String diagnosisKind,
            String purpose,
            String username) {

        String trimmedDiseaseCode = diseaseCode != null ? diseaseCode.trim() : "";
        String trimmedPrescriptionCode = prescriptionCode != null ? prescriptionCode.trim() : "";
        String trimmedPrescriptionName = prescriptionName != null ? prescriptionName.trim() : "";

        if (trimmedDiseaseCode.isBlank() || trimmedPrescriptionCode.isBlank() || trimmedPrescriptionName.isBlank()) {
            throw new IllegalArgumentException("상병코드, 처방코드, 처방명은 모두 필수입니다.");
        }

        CertificateAgentRequest agentRequest = CertificateAgentRequest.builder()
                .historyId(0)
                .certificateType(normalizeCertificateType(certificateType))
                .patientName("TEST-PATIENT")
                .patientAge(0)
                .patientGender("UNKNOWN")
                .entryDate(LocalDate.now().toString())
                .symptomDetail("XLSX 행 기반 생성 테스트 요청")
                .diagnosisKind(normalizeDiagnosisKind(diagnosisKind))
                .purpose(normalizePurpose(purpose))
                .diseases(List.of(CertificateAgentRequest.DiseaseInfo.builder()
                        .code(trimmedDiseaseCode)
                        .name(trimmedDiseaseCode)
                        .degree("N/A")
                        .build()))
                .diagnoses(List.of(CertificateAgentRequest.DiagnoseInfo.builder()
                        .code(trimmedPrescriptionCode)
                        .name(trimmedPrescriptionName)
                        .dose(1)
                        .time(1)
                        .days(1)
                        .build()))
                .build();

        String medicalCertificate = certificateAgentClient.generate(agentRequest)
                .map(r -> r.getMedicalCertificate())
                .filter(s -> s != null && !s.isBlank())
                .orElseGet(() -> buildDefaultCertificateTemplate(agentRequest));

        return buildGenerateResponse(username, medicalCertificate);
    }

    @Override
    public void saveCertificate(
            Integer historyId,
            MultipartFile pdfFile,
            boolean agentUsed,
            String originalMedicalCertificate,
            String savedMedicalCertificate,
            String feedbackType) {

        String pdfFilePath = null;

        if (pdfFile != null && !pdfFile.isEmpty()) {
            pdfFilePath = savePdfFile(historyId, pdfFile);
        }

        MedicalCertificateRecord record = new MedicalCertificateRecord();
        record.setHistoryId(historyId);
        record.setPdfFilePath(pdfFilePath);
        record.setAgentUsed(agentUsed);
        record.setOriginalMedicalCertificate(originalMedicalCertificate != null ? originalMedicalCertificate : "");
        record.setSavedMedicalCertificate(savedMedicalCertificate != null ? savedMedicalCertificate : "");
        record.setFeedbackType(feedbackType != null ? feedbackType : "NONE");
        record.setCreatedAt(LocalDateTime.now());

        medicalCertificateRepository.save(record);
        log.info("진단서 저장 완료 - historyId: {}, feedbackType: {}", historyId, feedbackType);
    }

    private String buildDefaultCertificateTemplate(CertificateAgentRequest req) {
        StringBuilder sb = new StringBuilder();
        boolean clinicalEstimate = "임상적 추정".equals(req.getDiagnosisKind());
        String diagnosisPhrase = clinicalEstimate ? "현재 임상 소견상 추정되는 상병에 대해" : "진단된 상병에 대해";
        if (req.getSymptomDetail() != null && !req.getSymptomDetail().isBlank()) {
            sb.append(req.getSymptomDetail()).append(" 증상과 관련하여 ");
        }
        sb.append(diagnosisPhrase).append(" 보존적 치료와 증상 조절을 위한 약물치료를 시행하였습니다. ");
        if (req.getDiagnoses() != null && !req.getDiagnoses().isEmpty()) {
            sb.append("현재 처방은 ");
            sb.append(req.getDiagnoses().stream()
                    .map(CertificateAgentRequest.DiagnoseInfo::getName)
                    .filter(name -> name != null && !name.isBlank())
                    .collect(Collectors.joining(", ")));
            sb.append(" 등을 통한 통증 및 염증 조절, 증상 완화를 목적으로 합니다. ");
        }
        sb.append("향후 증상 변화와 치료 반응을 확인하기 위해 재진 및 경과 관찰이 필요하며, 필요 시 추가 검사나 치료 조정이 권고됩니다. ");
        sb.append("증상이 지속되거나 악화되는 경우 의료진의 재평가를 받아 치료 계획을 조정해야 합니다.");
        return sb.toString();
    }

    private String normalizeCertificateType(String certificateType) {
        if ("MILITARY".equalsIgnoreCase(certificateType)) {
            return "MILITARY";
        }
        return "GENERAL";
    }

    private String normalizeDiagnosisKind(String diagnosisKind) {
        if (diagnosisKind == null || diagnosisKind.isBlank()) {
            return "미선택";
        }
        String trimmed = diagnosisKind.trim();
        if ("FINAL".equalsIgnoreCase(trimmed) || "최종진단".equals(trimmed.replace(" ", ""))) {
            return "최종 진단";
        }
        if ("CLINICAL_ESTIMATE".equalsIgnoreCase(trimmed)
                || "임상적추정".equals(trimmed.replace(" ", ""))) {
            return "임상적 추정";
        }
        return trimmed;
    }

    private String normalizePurpose(String purpose) {
        return purpose == null ? "" : purpose.trim();
    }

    private GenerateCertificateResponseDTO buildGenerateResponse(String username, String medicalCertificate) {
        String accessToken = jwtTokenProvider.generateAccessToken(username);
        String refreshToken = jwtTokenProvider.generateRefreshToken(username);

        GenerateCertificateResponseDTO response = new GenerateCertificateResponseDTO();
        response.setGrantType("Bearer");
        response.setAccessToken(accessToken);
        response.setRefreshToken(refreshToken);
        response.setMedicalCertificate(medicalCertificate);
        return response;
    }

    private String savePdfFile(int historyId, MultipartFile pdfFile) {
        try {
            Path dir = Paths.get(certificateStoragePath, String.valueOf(historyId));
            Files.createDirectories(dir);
            String filename = "certificate_" + System.currentTimeMillis() + ".pdf";
            Path dest = dir.resolve(filename);
            pdfFile.transferTo(dest);
            return certificateStoragePath + "/" + historyId + "/" + filename;
        } catch (IOException e) {
            log.error("PDF 파일 저장 실패 - historyId: {}", historyId, e);
            return null;
        }
    }

    private int calculateAge(LocalDate birth) {
        if (birth == null) return 0;
        return Period.between(birth, LocalDate.now()).getYears();
    }

    private LocalDateTime parseStartDateTime(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) return null;
        try {
            return LocalDate.parse(dateStr, DateTimeFormatter.ISO_LOCAL_DATE).atStartOfDay();
        } catch (Exception e) {
            return null;
        }
    }

    private LocalDateTime parseEndDateTime(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) return null;
        try {
            return LocalDate.parse(dateStr, DateTimeFormatter.ISO_LOCAL_DATE).atTime(LocalTime.MAX);
        } catch (Exception e) {
            return null;
        }
    }
}
