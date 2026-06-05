package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.ValidationAgentRequest;
import com.example.bitcomputer.model.ValidationAgentResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Slf4j
@Component
public class ValidationAgentClient {

    private final RestTemplate restTemplate;

    @Value("${ai.validation-agent.base-url:http://localhost:8002}")
    private String baseUrl;

    @Value("${ai.validation-agent.path:/api/agent/validation/run}")
    private String path;

    public ValidationAgentClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public ValidationAgentResponse validate(ValidationAgentRequest request) {
        String url = baseUrl + path;
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(java.util.List.of(MediaType.APPLICATION_JSON));

        ResponseEntity<ValidationAgentResponse> response = restTemplate.exchange(
                url,
                HttpMethod.POST,
                new HttpEntity<>(request, headers),
                ValidationAgentResponse.class);

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            throw new IllegalStateException("검증 에이전트 비정상 응답: " + response.getStatusCode());
        }
        log.info("검증 에이전트 호출 성공 - eventId={} status={}",
                request.getEventId(), response.getBody().getOverallStatus());
        return response.getBody();
    }
}
