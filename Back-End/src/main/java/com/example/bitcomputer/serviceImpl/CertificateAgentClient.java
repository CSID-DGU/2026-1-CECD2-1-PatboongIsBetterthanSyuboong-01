package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.CertificateAgentRequest;
import com.example.bitcomputer.model.CertificateAgentResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Optional;

/**
 * Python(FastAPI) 의 certificate_api 서비스를 호출하는 HTTP 클라이언트.
 *
 * <p>Gemini 기반 진단서 소견 생성은 Python 측에서 수행하므로, 여기서는
 * {@link CertificateAgentRequest} 를 POST 하고 {@link CertificateAgentResponse}
 * 를 돌려받기만 한다. Python 서버가 꺼져 있거나 LLM 호출이 실패하면
 * {@link Optional#empty()} 를 반환하여 상위 서비스가 폴백을 택할 수 있게 한다.
 */
@Slf4j
@Component
public class CertificateAgentClient {

    private final RestTemplate restTemplate;

    /**
     * 진단서 에이전트(certificate_api) 전용 base-url.
     *
     * <p>영상판독 Flask 서버(`ai.api.base-url`) 와 같은 포트(5000) 를 두고 충돌하던 문제를
     * 해결하기 위해 별도 프로퍼티로 분리했다. 미설정 시 5001 로 폴백한다.
     */
    @Value("${ai.certificate-agent.base-url:http://localhost:5001}")
    private String baseUrl;

    @Value("${ai.certificate-agent.path:/api/ai/document/generate}")
    private String path;

    public CertificateAgentClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * Python 에이전트에 진단서 생성을 요청한다.
     *
     * @param request Spring 이 MySQL 에서 조립한 환자·상병·처방 정보
     * @return Gemini 가 생성한 진단서 소견 문자열. 호출 실패 시 {@link Optional#empty()}.
     */
    public Optional<CertificateAgentResponse> generate(CertificateAgentRequest request) {
        String url = baseUrl + path;
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setAccept(List.of(MediaType.APPLICATION_JSON));
            HttpEntity<CertificateAgentRequest> entity = new HttpEntity<>(request, headers);

            ResponseEntity<CertificateAgentResponse> response = restTemplate.exchange(
                    url, HttpMethod.POST, entity, CertificateAgentResponse.class);

            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                log.info("Python 진단서 에이전트 호출 성공 - historyId={}", request.getHistoryId());
                return Optional.of(response.getBody());
            }
            log.warn("Python 진단서 에이전트 비정상 응답 - status={} body={}",
                    response.getStatusCode(), response.getBody());
            return Optional.empty();
        } catch (RestClientException e) {
            log.warn("Python 진단서 에이전트 호출 실패 ({}): {}", url, e.getMessage());
            return Optional.empty();
        } catch (Exception e) {
            log.error("Python 진단서 에이전트 호출 중 예상치 못한 오류 ({})", url, e);
            return Optional.empty();
        }
    }
}
