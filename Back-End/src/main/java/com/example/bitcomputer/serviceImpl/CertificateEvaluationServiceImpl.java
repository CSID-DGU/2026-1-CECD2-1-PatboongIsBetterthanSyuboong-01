package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.CertificateEvaluationResultDTO;
import com.example.bitcomputer.model.CertificateEvaluationResultDTO.PairDetail;
import com.example.bitcomputer.service.CertificateEvaluationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.*;
import java.util.Objects;
import java.util.stream.Collectors;

@Slf4j
@Service
public class CertificateEvaluationServiceImpl implements CertificateEvaluationService {

    private static final String GEMINI_API_URL =
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=";

    private static final String SYSTEM_INSTRUCTION =
            "당신은 AI가 작성한 진단서를 검수하는 독립적인 의료 전문 검수자입니다. "
            + "진단서를 작성한 AI와 당신은 완전히 별개입니다. "
            + "오직 의학적 근거에 기반해 공정하게 판단하세요.";

    // CoT + Few-shot
    private static final String NLI_PROMPT_TEMPLATE = """
            당신은 한국어 의료 NLI 평가를 수행합니다.
            [전제]는 환자의 증상·상병·특이사항이고, [가설]은 AI가 작성한 진단서의 소견 문장입니다.
            가설이 전제로부터 의학적으로 함의되는지 판단하세요.

            지시사항:
            1. "근거:" 로 시작하는 한 문장으로 의학적 판단 이유를 먼저 쓰세요.
            2. 그 다음 줄에 "판정:" 으로 시작하고 ENTAILMENT / NEUTRAL / CONTRADICTION 중 하나만 쓰세요.

            === 판정 기준 예시 (반드시 이 기준에 맞춰 판단) ===

            [예시 1 - ENTAILMENT]
            전제: 상병명: 고혈압(I10), 2형 당뇨병(E11), 치매, 뇌전증 / 특이사항: HTN, DM, 좌측 편마비 상태
            가설: 2형 당뇨병 혈당 조절을 위해 자누엠메트정50/500mg 처방을 유지합니다.
            근거: 2형 당뇨병(E11) 진단이 있으므로 DPP-4억제제·메트포르민 복합제 처방은 의학적으로 타당합니다.
            판정: ENTAILMENT

            [예시 2 - NEUTRAL]
            전제: 상병명: 폐렴(J18) / 특이사항: 알츠하이머 치매, 폐렴
            가설: 골다공증 예방을 위해 정기적인 골밀도(BMD) 검사 시행을 권고합니다.
            근거: 폐렴 및 치매 진단과 골밀도 검사 권고 사이에는 직접적인 의학적 연관이 없습니다.
            판정: NEUTRAL

            [예시 3 - CONTRADICTION]
            전제: 상병명: 갑상선 기능저하증(E03) / 특이사항: 당뇨, 저혈당 반복, 갑상선 저하증, 신장기능 저하
            가설: 혈당 조절 강화를 위해 인슐린 용량을 즉시 증량합니다.
            근거: 저혈당이 반복되는 환자에게 인슐린 증량을 제안하는 것은 저혈당 위험을 심화시키므로 의학적으로 모순입니다.
            판정: CONTRADICTION

            === 실제 평가 ===

            [전제]
            %s

            [가설]
            %s

            근거:
            판정:""";

    //문구 필터
    private static final List<String> SKIP_PATTERNS = List.of(
            "【", "】", "진단서", "주민등록", "위와 같이", "환자명", "성별", "나이",
            "진료일", "처방 내역", "상병명", "발행일", "의료기관", "의사명", "서명"
    );

    private final RestTemplate restTemplate;

    @Value("${gemini.api.key}")
    private String geminiApiKey;

    public CertificateEvaluationServiceImpl(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @Override
    public CertificateEvaluationResultDTO evaluate(
            String medicalCertificate,
            String diseaseCode,
            String prescriptionCode,
            String prescriptionName) {
        String premise = buildPremise(diseaseCode, prescriptionCode, prescriptionName);

        if (premise.isBlank()) {
            throw new IllegalArgumentException("상병/처방 정보가 없어 평가할 수 없습니다.");
        }

        List<String> sentences = splitIntoOpinionSentences(medicalCertificate);

        List<PairDetail> details = new ArrayList<>();
        int entailmentCount = 0;

        for (int i = 0; i < sentences.size(); i++) {
            String hypothesis = sentences.get(i);
            GeminiNliResult result = callGeminiOnce(premise, hypothesis);

            details.add(PairDetail.builder()
                    .index(i + 1)
                    .hypothesis(hypothesis)
                    .judgment(result.judgment())
                    .reason(result.reason())
                    .build());

            if ("ENTAILMENT".equals(result.judgment())) {
                entailmentCount++;
            }
        }

        int totalPairs = sentences.size();
        double score = totalPairs == 0 ? 0.0 : (double) entailmentCount / totalPairs;

        return CertificateEvaluationResultDTO.builder()
                .score(Math.round(score * 1000.0) / 1000.0)
                .entailmentCount(entailmentCount)
                .totalPairs(totalPairs)
                .premise(premise)
                .details(details)
                .build();
    }

    private String buildPremise(String diseaseCode, String prescriptionCode, String prescriptionName) {
        StringBuilder sb = new StringBuilder();
        if (diseaseCode != null && !diseaseCode.isBlank()) {
            sb.append("상병코드: ").append(diseaseCode.trim());
        }
        if (prescriptionCode != null && !prescriptionCode.isBlank()) {
            if (!sb.isEmpty()) sb.append("\n");
            sb.append("처방코드: ").append(prescriptionCode.trim());
        }
        if (prescriptionName != null && !prescriptionName.isBlank()) {
            if (!sb.isEmpty()) sb.append("\n");
            sb.append("처방명: ").append(prescriptionName.trim());
        }
        return sb.toString();
    }
    
    private List<String> splitIntoOpinionSentences(String text) {
        if (text == null || text.isBlank()) return List.of();
        return Arrays.stream(text.split("(?<=[.!?。])|\\n+"))
                .map(String::trim)
                .filter(s -> s.length() >= 10)
                .filter(s -> SKIP_PATTERNS.stream().noneMatch(s::contains))
                .collect(Collectors.toList());
    }

    // Gemini 호출
    @SuppressWarnings({"unchecked", "rawtypes"})
    private GeminiNliResult callGeminiOnce(String premise, String hypothesis) {
        String prompt = NLI_PROMPT_TEMPLATE.formatted(premise, hypothesis);
        String url = GEMINI_API_URL + geminiApiKey;

        Map<String, Object> requestBody = Map.of(
                "systemInstruction", Map.of(
                        "parts", List.of(Map.of("text", SYSTEM_INSTRUCTION))
                ),
                "contents", List.of(
                        Map.of("parts", List.of(Map.of("text", prompt)))
                ),
                "generationConfig", Map.of(
                        "temperature", 0.0,
                        "maxOutputTokens", 150
                )
        );

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);

            ResponseEntity<Map> response = restTemplate.exchange(url, HttpMethod.POST, entity, Map.class);

            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                List<Map> candidates = (List<Map>) response.getBody().get("candidates");
                if (candidates != null && !candidates.isEmpty()) {
                    Map content = (Map) candidates.get(0).get("content");
                    List<Map> parts = (List<Map>) content.get("parts");
                    if (parts != null && !parts.isEmpty()) {
                        String raw = Objects.toString(parts.get(0).get("text"), "").trim();
                        return parseCoTResponse(raw);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("Gemini NLI 호출 실패 - hypothesis: [{}], error: {}", hypothesis, e.getMessage());
        }

        return new GeminiNliResult("NEUTRAL", "");
    }

    private GeminiNliResult parseCoTResponse(String raw) {
        String reason = "";
        String judgment = "NEUTRAL";

        for (String line : raw.split("\\n")) {
            String trimmed = line.trim();
            if (trimmed.startsWith("근거:")) {
                reason = trimmed.substring("근거:".length()).trim();
            } else if (trimmed.startsWith("판정:")) {
                String upper = trimmed.toUpperCase();
                if (upper.contains("ENTAILMENT")) judgment = "ENTAILMENT";
                else if (upper.contains("CONTRADICTION")) judgment = "CONTRADICTION";
                else judgment = "NEUTRAL";
            }
        }

        // "근거:" 없이 ENTAILMENT/CONTRADICTION/NEUTRAL만 반환한 경우 fallback
        if (reason.isEmpty()) {
            String upper = raw.toUpperCase();
            if (upper.contains("ENTAILMENT")) judgment = "ENTAILMENT";
            else if (upper.contains("CONTRADICTION")) judgment = "CONTRADICTION";
        }

        return new GeminiNliResult(judgment, reason);
    }

    private record GeminiNliResult(String judgment, String reason) {}
}
