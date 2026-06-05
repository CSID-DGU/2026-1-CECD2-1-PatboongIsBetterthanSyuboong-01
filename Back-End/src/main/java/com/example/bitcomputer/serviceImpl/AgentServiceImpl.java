package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.HistoryDiagnoseRepository;
import com.example.bitcomputer.Repository.HistoryDiseaseRepository;
import com.example.bitcomputer.Repository.HistoryRepository;
import com.example.bitcomputer.Repository.PatientRepository;
import com.example.bitcomputer.Repository.DiagnoseRepository;
import com.example.bitcomputer.Repository.PrescriptionFeedbackRepository;
import com.example.bitcomputer.Repository.RadiologyReportRepository;
import com.example.bitcomputer.Repository.ValidationJobRepository;
import com.example.bitcomputer.entity.Diagnose;
import com.example.bitcomputer.entity.History;
import com.example.bitcomputer.entity.HistoryDiagnose;
import com.example.bitcomputer.entity.HistoryDisease;
import com.example.bitcomputer.entity.Patient;
import com.example.bitcomputer.entity.PrescriptionFeedback;
import com.example.bitcomputer.entity.RadiologyReport;
import com.example.bitcomputer.entity.ValidationJob;
import com.example.bitcomputer.entity.ValidationJobStatus;
import com.example.bitcomputer.model.HistoryDTO;
import com.example.bitcomputer.model.PrescriptionAgentRequest;
import com.example.bitcomputer.model.PrescriptionAgentResponse;
import com.example.bitcomputer.model.PrescriptionRecommendRequestDTO;
import com.example.bitcomputer.model.PrescriptionRecommendResponseDTO;
import com.example.bitcomputer.model.RecommendedPrescriptionItemDTO;
import com.example.bitcomputer.model.SavePrescriptionFeedbackRequestDTO;
import com.example.bitcomputer.model.ValidationJobStartResponseDTO;
import com.example.bitcomputer.service.AgentService;
import com.example.bitcomputer.service.HistoryService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
public class AgentServiceImpl implements AgentService {

    private static final DateTimeFormatter ENTRY_FMT = DateTimeFormatter.ISO_LOCAL_DATE;

    private final HistoryService historyService;
    private final HistoryDiagnoseRepository historyDiagnoseRepository;
    private final HistoryRepository historyRepository;
    private final HistoryDiseaseRepository historyDiseaseRepository;
    private final PatientRepository patientRepository;
    private final DiagnoseRepository diagnoseRepository;
    private final PrescriptionFeedbackRepository prescriptionFeedbackRepository;
    private final RadiologyReportRepository radiologyReportRepository;
    private final ValidationJobRepository validationJobRepository;
    private final PrescriptionAgentClient prescriptionAgentClient;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Value("${validation.rabbitmq.request-queue:validation.prescription.request}")
    private String validationRequestQueue;

    @Value("${ai.prescription-agent.fetch-top-rx-from-arango:true}")
    private boolean fetchTopRxFromArango;

    @Value("${ai.prescription-agent.arango-top-rx-limit:80}")
    private int arangoTopRxLimit;

    @Value("${ai.prescription-agent.fetch-cohort-rx-from-arango:true}")
    private boolean fetchCohortRxFromArango;

    @Value("${ai.prescription-agent.arango-cohort-rx-limit:40}")
    private int arangoCohortRxLimit;

    @Value("${ai.prescription-agent.example-context-path:../GraphDB/langchain_graph_qa/patient_ctx.example.json}")
    private String exampleContextPath;

    public AgentServiceImpl(
            HistoryService historyService,
            HistoryDiagnoseRepository historyDiagnoseRepository,
            HistoryRepository historyRepository,
            HistoryDiseaseRepository historyDiseaseRepository,
            PatientRepository patientRepository,
            DiagnoseRepository diagnoseRepository,
            PrescriptionFeedbackRepository prescriptionFeedbackRepository,
            RadiologyReportRepository radiologyReportRepository,
            ValidationJobRepository validationJobRepository,
            ObjectMapper objectMapper,
            PrescriptionAgentClient prescriptionAgentClient,
            RabbitTemplate rabbitTemplate) {
        this.historyService = historyService;
        this.historyDiagnoseRepository = historyDiagnoseRepository;
        this.historyRepository = historyRepository;
        this.historyDiseaseRepository = historyDiseaseRepository;
        this.patientRepository = patientRepository;
        this.diagnoseRepository = diagnoseRepository;
        this.prescriptionFeedbackRepository = prescriptionFeedbackRepository;
        this.radiologyReportRepository = radiologyReportRepository;
        this.validationJobRepository = validationJobRepository;
        this.objectMapper = objectMapper;
        this.prescriptionAgentClient = prescriptionAgentClient;
        this.rabbitTemplate = rabbitTemplate;
    }

    @Override
    public ValidationJobStartResponseDTO recommendPrescription(PrescriptionRecommendRequestDTO request) {
        History currentHistory = resolveCurrentHistory(request);
        Patient patient = patientRepository.findById(currentHistory.getPatientId())
                .orElseThrow(() -> new EntityNotFoundException(
                        "Patient not found with id " + currentHistory.getPatientId()));
        String jobId = UUID.randomUUID().toString();
        Map<String, Object> payload = buildValidationJobPayload(jobId, currentHistory, patient, request);

        ValidationJob job = new ValidationJob();
        job.setJobId(jobId);
        job.setHistoryId(currentHistory.getId());
        job.setPatientId(currentHistory.getPatientId());
        job.setEmployeeId(currentHistory.getEmployeeId());
        job.setDeptId(currentHistory.getDeptId());
        job.setTriggerType("AI_PRESCRIPTION_RECOMMEND");
        job.setStatus(ValidationJobStatus.PENDING);
        job.setRequestPayloadJson(toJson(payload));
        validationJobRepository.save(job);

        rabbitTemplate.convertAndSend(validationRequestQueue, payload);
        log.info("AI 처방 추천/검증 job 발행 - jobId={} historyId={}", jobId, currentHistory.getId());

        return ValidationJobStartResponseDTO.builder()
                .jobId(jobId)
                .historyId(currentHistory.getId())
                .status(ValidationJobStatus.PENDING)
                .build();
    }

    private Map<String, Object> buildValidationJobPayload(
            String jobId,
            History history,
            Patient patient,
            PrescriptionRecommendRequestDTO request) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("jobId", jobId);
        payload.put("eventId", 0);
        payload.put("eventType", "AI_PRESCRIPTION_RECOMMEND");
        payload.put("triggerType", "AI_PRESCRIPTION_RECOMMEND");
        payload.put("historyId", history.getId());
        payload.put("patientId", history.getPatientId());
        payload.put("employeeId", history.getEmployeeId());
        payload.put("deptId", history.getDeptId());
        payload.put("symptoms", history.getSymptomDetail());
        payload.put("createdAt", LocalDateTime.now(ZoneId.of("Asia/Seoul")).toString());
        Map<String, Object> patientSummary = new LinkedHashMap<>();
        patientSummary.put("patientId", history.getPatientId());
        patientSummary.put("name", patient.getName());
        patientSummary.put("gender", patient.getGender());
        patientSummary.put("birth", patient.getBirth() != null ? patient.getBirth().toString() : "");
        patientSummary.put("visitNumber", patient.getVisitNumber() != null ? patient.getVisitNumber() : "");
        payload.put("patientSummary", patientSummary);
        payload.put("savedDiseases", toDiseaseRows(historyDiseaseRepository.findByHistoryId(history.getId()), request));
        payload.put("savedPrescriptions", toPrescriptionRows(historyDiagnoseRepository.findByHistoryId(history.getId())));
        payload.put("xrayInference", loadLatestXrayInference(history.getPatientId()));
        return payload;
    }

    private List<Map<String, Object>> toDiseaseRows(
            List<HistoryDisease> diseases,
            PrescriptionRecommendRequestDTO request) {
        List<Map<String, Object>> rows = diseases.stream()
                .map(disease -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", disease.getId());
                    row.put("code", disease.getCode());
                    row.put("name", disease.getName());
                    row.put("degree", disease.getDegree());
                    return row;
                })
                .collect(Collectors.toCollection(ArrayList::new));
        if (!rows.isEmpty() || request.getDiseaseCodes() == null) {
            return rows;
        }
        for (String code : request.getDiseaseCodes()) {
            if (code == null || code.isBlank()) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("code", code.trim());
            row.put("name", code.trim());
            row.put("degree", "");
            rows.add(row);
        }
        return rows;
    }

    private List<Map<String, Object>> toPrescriptionRows(List<HistoryDiagnose> diagnoses) {
        return diagnoses.stream()
                .map(diagnose -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", diagnose.getId());
                    row.put("code", diagnose.getCode());
                    row.put("name", diagnose.getName());
                    row.put("dose", diagnose.getDose());
                    row.put("time", diagnose.getTime());
                    row.put("days", diagnose.getDays());
                    return row;
                })
                .toList();
    }

    private Map<String, Object> loadLatestXrayInference(int patientId) {
        return radiologyReportRepository
                .findFirstByPatientIdAndStatusOrderByEntryDateDescRadiologyRequestIdDesc(patientId, "completed")
                .map(this::toXrayInference)
                .orElse(null);
    }

    private Map<String, Object> toXrayInference(RadiologyReport report) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("radiologyRequestId", report.getRadiologyRequestId());
        out.put("result", report.getResult());
        out.put("predictedDiseases", parsePredictedDiseases(report.getSummary()));
        out.put("heatmapUrl", report.getImageUrl());
        out.put("status", report.getStatus());
        out.put("entryDate", report.getEntryDate());
        return out;
    }

    private Object parsePredictedDiseases(String summary) {
        if (summary == null || summary.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(summary, Object.class);
        } catch (Exception e) {
            return summary;
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("validation job payload 직렬화 실패", e);
        }
    }

    @SuppressWarnings("unchecked")
    private void applyExampleContextIfRequested(
            PrescriptionAgentRequest agentRequest,
            PrescriptionRecommendRequestDTO request) {
        if (!Boolean.TRUE.equals(request.getUseExampleContext())) {
            return;
        }
        try {
            Path path = Path.of(exampleContextPath);
            if (!path.isAbsolute()) {
                path = Path.of("").toAbsolutePath().resolve(path).normalize();
            }
            if (!Files.exists(path)) {
                log.warn("example context 파일이 없어 기본 컨텍스트를 사용합니다: {}", path);
                return;
            }

            Map<String, Object> ctx = objectMapper.readValue(path.toFile(), Map.class);
            /*
             * 화면에서 넘긴 내원번호(arango_patient_id)는 Arango visits 매칭에 직결되므로
             * 예제 JSON의 patient_id로 덮어쓰지 않는다. (예제는 증상/이력 텍스트용)
             */
            boolean hasArangoPatientOverride = request.getArangoPatientId() != null
                    && !request.getArangoPatientId().isBlank();
            Object patientId = ctx.get("patient_id");
            if (!hasArangoPatientOverride && patientId != null) {
                agentRequest.setPatientId(String.valueOf(patientId));
            }
            if (ctx.get("symptoms") != null) {
                agentRequest.setSymptoms(String.valueOf(ctx.get("symptoms")));
            }
            if (ctx.get("history") != null) {
                agentRequest.setHistory(String.valueOf(ctx.get("history")));
            }
            /*
             * arango_patient_id 가 있으면 그래프/MySQL 기반 처방·유사 사례를 쓰는 경로이므로
             * 예제 파일의 similar_outcomes·top_rx 로 덮어쓰지 않는다. (예제는 증상·이력 텍스트 보조용)
             */
            if (!hasArangoPatientOverride && ctx.get("similar_outcomes") != null) {
                agentRequest.setSimilarOutcomes(String.valueOf(ctx.get("similar_outcomes")));
            }
            /*
             * 예제 JSON에 top_rx: []만 있으면 MySQL에서 채운 처방·이후 Arango 보강을 망가뜨리므로
             * 비어 있을 때는 기존 agentRequest.top_rx 를 유지한다.
             */
            Object topRx = ctx.get("top_rx");
            if (!hasArangoPatientOverride
                    && topRx instanceof List<?> topRxList
                    && !topRxList.isEmpty()) {
                agentRequest.setTopRx((List<Map<String, Object>>) topRxList);
            }
            Object mentionLinks = ctx.get("mention_links");
            if (mentionLinks instanceof List<?> mentionList && !mentionList.isEmpty()) {
                agentRequest.setMentionLinks((List<Map<String, Object>>) mentionList);
            }
            log.info(
                    "AI 추천에 example context 적용: {} (arango_patient_id 지정 시 예제 top_rx·similar_outcomes 미적용: {})",
                    path,
                    hasArangoPatientOverride);
        } catch (Exception e) {
            log.warn("example context 적용 실패, 기본 컨텍스트 사용: {}", e.getMessage());
        }
    }

    private History resolveCurrentHistory(PrescriptionRecommendRequestDTO request) {
        if (request.getHistoryId() != null) {
            return historyRepository.findById(request.getHistoryId())
                    .orElseThrow(() -> new EntityNotFoundException(
                            "History not found with id " + request.getHistoryId()));
        }
        if (request.getHistoryDiagnoseId() != null) {
            HistoryDiagnose hd = historyDiagnoseRepository.findById(request.getHistoryDiagnoseId())
                    .orElseThrow(() -> new EntityNotFoundException(
                            "HistoryDiagnose not found with id " + request.getHistoryDiagnoseId()));
            return historyRepository.findById(hd.getHistoryId())
                    .orElseThrow(() -> new EntityNotFoundException(
                            "History not found with id " + hd.getHistoryId()));
        }
        throw new IllegalArgumentException("history_id 또는 history_diagnose_id 중 하나는 필수입니다.");
    }

    /**
     * 요청 본문의 disease_codes 가 있으면 우선하고, 없으면 현재 진료에 저장된 상병(HistoryDisease) 코드를 사용한다.
     */
    private List<String> resolveDiseaseCodes(History current, PrescriptionRecommendRequestDTO request) {
        LinkedHashSet<String> out = new LinkedHashSet<>();
        if (request.getDiseaseCodes() != null) {
            for (String c : request.getDiseaseCodes()) {
                if (c != null && !c.isBlank()) {
                    out.add(c.trim());
                }
            }
        }
        if (!out.isEmpty()) {
            return new ArrayList<>(out);
        }
        List<HistoryDisease> rows = historyDiseaseRepository.findByHistoryId(current.getId());
        for (HistoryDisease d : rows) {
            if (d.getCode() != null && !d.getCode().isBlank()) {
                out.add(d.getCode().trim());
            }
        }
        return new ArrayList<>(out);
    }

    /**
     * MySQL 에서 모은 환자 feature 를 Python / ArangoDB 가 기대하는 스키마로 변환한다.
     *
     * <ul>
     *   <li>{@code patient_id} — Arango visits 의 {@code 내원번호_norm} 과 매칭되는 문자열.
     *       현재 스키마에서는 {@link Patient#getIdentityNumber()} 또는 fallback 으로 {@code patient.id}.</li>
     *   <li>{@code symptoms} — 현재 진료의 증상 기술(symptomDetail).</li>
     *   <li>{@code history} — 과거 진료들의 entry_date / symptom / memo 를 여러 줄로 합친 문자열.</li>
     *   <li>{@code top_rx} — 과거 History 에 적재된 HistoryDiagnose 를 Arango 스키마 키
     *       ({@code 내원번호, 처방시퀀스, 처방코드, 처방명}) 로 펼친다.</li>
     * </ul>
     */
    private PrescriptionAgentRequest buildAgentRequest(
            Patient patient,
            History current,
            List<HistoryDTO> histories,
            String arangoPatientIdOverride,
            List<String> diseaseCodes) {

        String patientIdForGraph = resolvePatientIdForGraph(patient, arangoPatientIdOverride);

        List<Map<String, Object>> topRx = buildTopRx(histories);
        String historyText = buildHistoryText(current, histories);
        String symptoms = current.getSymptomDetail() != null ? current.getSymptomDetail() : "";

        return PrescriptionAgentRequest.builder()
                .patientId(patientIdForGraph)
                .symptoms(symptoms)
                .history(historyText)
                .topRx(topRx)
                .similarOutcomes("")
                .fetchTopRxFromArango(fetchTopRxFromArango)
                .arangoTopRxLimit(arangoTopRxLimit)
                .diseaseCodes(diseaseCodes.isEmpty() ? null : diseaseCodes)
                .fetchCohortRxFromArango(fetchCohortRxFromArango)
                .arangoCohortRxLimit(arangoCohortRxLimit)
                .build();
    }

    private String resolvePatientIdForGraph(Patient patient, String override) {
        if (override != null && !override.isBlank()) {
            return override.trim();
        }
        // TODO(매핑): 실제 EMR 의 "내원번호" 컬럼이 추가되면 그 값을 우선 사용하도록 바꿀 것.
        //   지금은 identityNumber → patient.id 순으로 후보를 넘기고, Python 쪽에서
        //   내원번호_norm / visit_id / _key 중 어느 키로든 매칭되게 되어 있음.
        if (patient.getIdentityNumber() != null && !patient.getIdentityNumber().isBlank()) {
            return patient.getIdentityNumber().trim();
        }
        return String.valueOf(patient.getId());
    }

    private List<Map<String, Object>> buildTopRx(List<HistoryDTO> histories) {
        if (histories == null || histories.isEmpty()) {
            return new ArrayList<>();
        }
        List<Integer> historyIds = histories.stream()
                .map(HistoryDTO::getId)
                .filter(java.util.Objects::nonNull)
                .toList();
        if (historyIds.isEmpty()) {
            return new ArrayList<>();
        }
        List<HistoryDiagnose> diagnoses = historyDiagnoseRepository.findByHistoryIdIn(historyIds);
        List<Map<String, Object>> rows = new ArrayList<>(diagnoses.size());
        for (HistoryDiagnose d : diagnoses) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("내원번호", String.valueOf(d.getHistoryId()));
            row.put("처방시퀀스", String.valueOf(d.getId()));
            row.put("처방코드", d.getCode());
            row.put("처방명", d.getName());
            row.put("dose", d.getDose());
            row.put("time", d.getTime());
            row.put("days", d.getDays());
            rows.add(row);
        }
        return rows;
    }

    private String buildHistoryText(History current, List<HistoryDTO> histories) {
        StringBuilder sb = new StringBuilder();

        // 현재 진료 상병/질환 기록
        List<HistoryDisease> currentDiseases = historyDiseaseRepository.findByHistoryId(current.getId());
        if (!currentDiseases.isEmpty()) {
            sb.append("[현재 진료 상병] ");
            for (int i = 0; i < currentDiseases.size(); i++) {
                HistoryDisease d = currentDiseases.get(i);
                if (i > 0) sb.append(", ");
                sb.append(d.getCode()).append(":").append(d.getName());
                if (d.getDegree() != null && !d.getDegree().isBlank()) {
                    sb.append("(").append(d.getDegree()).append(")");
                }
            }
            sb.append('\n');
        }
        if (current.getMemo() != null && !current.getMemo().isBlank()) {
            sb.append("[현재 메모] ").append(current.getMemo()).append('\n');
        }

        // 과거 진료 요약
        if (histories != null) {
            int appended = 0;
            for (HistoryDTO h : histories) {
                if (h.getId() != null && h.getId() == current.getId()) {
                    continue; // 현재 진료는 위에서 이미 처리
                }
                String line = formatPastHistoryLine(h);
                if (line != null) {
                    sb.append(line).append('\n');
                    appended++;
                }
                if (appended >= 10) {
                    // 프롬프트 폭주 방지
                    break;
                }
            }
        }

        return sb.toString().trim();
    }

    private String formatPastHistoryLine(HistoryDTO h) {
        StringBuilder line = new StringBuilder("[과거 진료");
        if (h.getEntryDate() != null) {
            line.append(" ")
                    .append(ENTRY_FMT.format(
                            h.getEntryDate().toInstant()
                                    .atZone(java.time.ZoneId.systemDefault())
                                    .toLocalDate()));
        }
        line.append("] ");
        boolean hasContent = false;
        if (h.getSymptomDetail() != null && !h.getSymptomDetail().isBlank()) {
            line.append("증상=").append(h.getSymptomDetail().trim());
            hasContent = true;
        }
        if (h.getMemo() != null && !h.getMemo().isBlank()) {
            if (hasContent) line.append(" / ");
            line.append("메모=").append(h.getMemo().trim());
            hasContent = true;
        }
        return hasContent ? line.toString() : null;
    }

    private List<RecommendedPrescriptionItemDTO> callAgentAndMap(PrescriptionAgentRequest request) {
        Optional<PrescriptionAgentResponse> maybe = prescriptionAgentClient.recommend(request);
        if (maybe.isEmpty()) {
            log.warn(
                    "처방 추천 에이전트 응답 없음 — Python prescription_api(기본 :8001) 가동·URL(ai.prescription-agent.base-url)·"
                            + "네트워크를 확인하세요. (Spring 6 이전에는 200 OK 인데도 상태코드 비교 실패로 비어 보일 수 있음)");
            return Collections.emptyList();
        }
        PrescriptionAgentResponse resp = maybe.get();
        if (resp.getPrescriptions() == null || resp.getPrescriptions().isEmpty()) {
            log.warn("처방 추천 Python 응답 본문은 있으나 prescriptions 가 비어 있음");
            return Collections.emptyList();
        }
        List<RecommendedPrescriptionItemDTO> out = new ArrayList<>(resp.getPrescriptions().size());
        for (PrescriptionAgentResponse.Item item : resp.getPrescriptions()) {
            Diagnose matched = findDiagnoseMaster(item);
            out.add(RecommendedPrescriptionItemDTO.builder()
                    .id(matched != null ? matched.getId() : 0)
                    .rank(item.getRank())
                    .prescriptionCode(item.getPrescriptionCode())
                    .prescriptionName(item.getName())
                    .reason(item.getReason())
                    .confidenceScore(item.getConfidenceScore() != null ? item.getConfidenceScore() : 0.0)
                    .dose(matched != null ? matched.getDose() : 0)
                    .time(matched != null ? matched.getTime() : 0)
                    .days(matched != null ? matched.getDays() : 0)
                    .build());
        }
        return out;
    }

    private Diagnose findDiagnoseMaster(PrescriptionAgentResponse.Item item) {
        if (item.getPrescriptionCode() != null && !item.getPrescriptionCode().isBlank()) {
            Optional<Diagnose> byCode = diagnoseRepository.findByCode(item.getPrescriptionCode().trim());
            if (byCode.isPresent()) {
                return byCode.get();
            }
        }
        if (item.getName() != null && !item.getName().isBlank()) {
            Optional<Diagnose> byName = diagnoseRepository.findByName(item.getName().trim());
            if (byName.isPresent()) {
                return byName.get();
            }
        }
        return createDiagnoseMasterFromAgentItem(item);
    }

    private Diagnose createDiagnoseMasterFromAgentItem(PrescriptionAgentResponse.Item item) {
        String code = normalizeText(item.getPrescriptionCode());
        String name = normalizeText(item.getName());

        if (code == null && name == null) {
            return null;
        }
        if (code == null) {
            code = "AUTO-" + Math.abs(name.hashCode());
        }
        if (name == null) {
            name = code;
        }

        try {
            Diagnose entity = new Diagnose();
            entity.setCode(code);
            entity.setName(name);
            entity.setDose(0);
            entity.setTime(0);
            entity.setDays(0);
            Diagnose saved = diagnoseRepository.save(entity);
            log.info("AI 추천 처방을 diagnose 마스터에 자동 등록 - id={} code={} name={}", saved.getId(), code, name);
            return saved;
        } catch (Exception e) {
            log.warn("AI 추천 처방 diagnose 자동 등록 실패 - code={} name={} err={}", code, name, e.getMessage());
            Optional<Diagnose> byCode = diagnoseRepository.findByCode(code);
            if (byCode.isPresent()) {
                return byCode.get();
            }
            return diagnoseRepository.findByName(name).orElse(null);
        }
    }

    private String normalizeText(String v) {
        if (v == null) {
            return null;
        }
        String t = v.trim();
        if (t.isEmpty() || "미기재".equals(t)) {
            return null;
        }
        return t;
    }

    @Override
    @org.springframework.transaction.annotation.Transactional
    public void savePrescriptionFeedback(SavePrescriptionFeedbackRequestDTO request) {
        if (request.getHistoryId() == null || request.getFeedbackItems() == null || request.getFeedbackItems().isEmpty()) {
            throw new IllegalArgumentException("historyId and feedbackItems are required");
        }

        boolean hasMissed = request.getFeedbackItems().stream().anyMatch(i -> "missed".equals(i.getStatus()));
        boolean hasAiStatuses = request.getFeedbackItems().stream()
                .anyMatch(i -> "accepted".equals(i.getStatus()) || "rejected".equals(i.getStatus()));

        // missed와 accepted/rejected는 서로를 지우지 않도록 분리 삭제
        if (hasMissed) {
            prescriptionFeedbackRepository.deleteMissedByHistoryId(request.getHistoryId());
        }
        if (hasAiStatuses) {
            prescriptionFeedbackRepository.deleteNonMissedByHistoryId(request.getHistoryId());
        }

        LocalDateTime now = LocalDateTime.now();
        List<PrescriptionFeedback> entities = request.getFeedbackItems().stream()
                .map(item -> {
                    PrescriptionFeedback fb = new PrescriptionFeedback();
                    fb.setHistoryId(request.getHistoryId());
                    fb.setHistoryDiagnoseId(request.getHistoryDiagnoseId());
                    fb.setRank(item.getRank());
                    fb.setPrescriptionId(item.getPrescriptionId());
                    fb.setPrescriptionCode(item.getPrescriptionCode());
                    fb.setPrescriptionName(item.getPrescriptionName());
                    fb.setConfidenceScore(item.getConfidenceScore());
                    fb.setReason(item.getReason());
                    fb.setStatus(item.getStatus());
                    fb.setCreatedAt(now);
                    return fb;
                })
                .collect(Collectors.toList());
        prescriptionFeedbackRepository.saveAll(entities);
        try {
            prescriptionAgentClient.saveFeedbackToGraph(request);
        } catch (Exception e) {
            // MySQL 저장 성공은 유지하고, 그래프 적재 실패는 경고로 남긴다.
            log.warn("Arango 처방 피드백 저장 실패: historyId={}, err={}", request.getHistoryId(), e.getMessage());
        }
        log.info("처방 피드백 저장: historyId={}, accepted={}, rejected={}, missed={}",
                request.getHistoryId(),
                entities.stream().filter(e -> "accepted".equals(e.getStatus())).count(),
                entities.stream().filter(e -> "rejected".equals(e.getStatus())).count(),
                entities.stream().filter(e -> "missed".equals(e.getStatus())).count());
    }
}
