package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.SavePrescriptionFeedbackRequestDTO;
import com.example.bitcomputer.model.PrescriptionAgentRequest;
import com.example.bitcomputer.model.PrescriptionAgentResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Python(FastAPI) 의 prescription_api 서비스를 호출하는 HTTP 클라이언트.
 *
 * <p>ArangoDB 그래프를 포함한 LLM 프롬프트는 Python 측에서 조립하므로, 여기서는
 * {@link PrescriptionAgentRequest} 를 POST 하고 {@link PrescriptionAgentResponse}
 * 를 돌려받기만 한다. Python 서버가 꺼져 있거나 LLM 호출이 실패하면
 * {@link Optional#empty()} 를 반환하여 상위 서비스가 폴백을 택할 수 있게 한다.
 */
@Slf4j
@Component
public class PrescriptionAgentClient {

    private final RestTemplate restTemplate;

    @Value("${ai.prescription-agent.base-url:http://localhost:8001}")
    private String baseUrl;

    @Value("${ai.prescription-agent.path:/api/agent/prescription/recommend}")
    private String path;

    @Value("${ai.prescription-agent.feedback-path:/api/agent/prescription/feedback}")
    private String feedbackPath;

    public PrescriptionAgentClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * Python 에이전트에 처방 추천을 요청한다.
     *
     * @param request Spring 이 MySQL + (선택) Arango 에서 만든 feature 번들
     * @return LLM 이 생성한 3건 추천. 호출 실패 시 {@link Optional#empty()}.
     */
    public Optional<PrescriptionAgentResponse> recommend(PrescriptionAgentRequest request) {
        String url = baseUrl + path;
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setAccept(java.util.List.of(MediaType.APPLICATION_JSON));
            HttpEntity<PrescriptionAgentRequest> entity = new HttpEntity<>(request, headers);

            ResponseEntity<PrescriptionAgentResponse> response = restTemplate.exchange(
                    url, HttpMethod.POST, entity, PrescriptionAgentResponse.class);

            // Spring 6: getStatusCode() 는 HttpStatusCode 이므로 == HttpStatus.OK 비교는 실패할 수 있음
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                PrescriptionAgentResponse body = response.getBody();
                log.info(
                        "Python 처방 에이전트 호출 성공 - patient_id={} disease_codes={} used_arango={} "
                                + "top_rx_count={} used_cohort={} cohort_count={} rx={}",
                        request.getPatientId(),
                        request.getDiseaseCodes(),
                        body.getUsedArangoTopRx(),
                        body.getArangoTopRxCount(),
                        body.getUsedCohortRx(),
                        body.getCohortRxCount(),
                        body.getPrescriptions() != null ? body.getPrescriptions().size() : 0);
                return Optional.of(body);
            }
            log.warn(
                    "Python 처방 에이전트 비정상 응답 - status={} body={}",
                    response.getStatusCode(), response.getBody());
            return Optional.empty();
        } catch (RestClientException e) {
            log.warn("Python 처방 에이전트 호출 실패 ({}): {}", url, e.getMessage());
            return Optional.empty();
        } catch (Exception e) {
            log.error("Python 처방 에이전트 호출 중 예상치 못한 오류 ({})", url, e);
            return Optional.empty();
        }
    }

    public void saveFeedbackToGraph(SavePrescriptionFeedbackRequestDTO request) {
        String url = baseUrl + feedbackPath;
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(java.util.List.of(MediaType.APPLICATION_JSON));

        List<Map<String, Object>> feedbackItems = new ArrayList<>();
        for (SavePrescriptionFeedbackRequestDTO.FeedbackItem item : request.getFeedbackItems()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("rank", item.getRank());
            row.put("prescription_id", item.getPrescriptionId());
            row.put("prescription_code", item.getPrescriptionCode());
            row.put("prescription_name", item.getPrescriptionName());
            row.put("confidence_score", item.getConfidenceScore());
            row.put("reason", item.getReason());
            row.put("status", item.getStatus());
            feedbackItems.add(row);
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("history_id", request.getHistoryId());
        payload.put("history_diagnose_id", request.getHistoryDiagnoseId());
        payload.put("feedback_items", feedbackItems);

        try {
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(payload, headers);
            ResponseEntity<Map> response = restTemplate.exchange(
                    url, HttpMethod.POST, entity, Map.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new IllegalStateException(
                        "그래프 피드백 API 비정상 응답 status=" + response.getStatusCode());
            }
        } catch (RestClientException e) {
            throw new IllegalStateException("그래프 피드백 API 호출 실패: " + e.getMessage(), e);
        }
    }
}
