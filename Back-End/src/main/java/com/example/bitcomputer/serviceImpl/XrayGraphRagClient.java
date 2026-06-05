package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.RadiologyAnalysisResponseDTO;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

@Slf4j
@Component
public class XrayGraphRagClient {

    private static final Set<String> EXCLUDED_DISEASE_TAGS = Set.of("no_finding", "support_devices");
    private static final int MAX_PREDICTED_DISEASES = 3;

    private final RestTemplate restTemplate;

    @Value("${xray.api.base-url:http://localhost:8000}")
    private String baseUrl;

    @Value("${xray.api.public-base-url:${xray.api.base-url:http://localhost:8000}}")
    private String publicBaseUrl;

    @Value("${xray.api.path:/infer}")
    private String path;

    @Value("${xray.api.default-view:AP}")
    private String defaultView;

    @Value("${xray.api.top-k:10}")
    private int topK;

    public XrayGraphRagClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public RadiologyAnalysisResponseDTO infer(Path imagePath, String view) {
        String url = baseUrl + path;
        String effectiveView = normalizeView(view);
        log.info("XrayGraphRAG 호출 시작 - URL: {}, image={}, view={}", url, imagePath, effectiveView);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("image", new FileSystemResource(imagePath));
        body.add("view", effectiveView);
        body.add("topK", topK);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        HttpEntity<MultiValueMap<String, Object>> entity = new HttpEntity<>(body, headers);

        ResponseEntity<XrayInferResponse> response = restTemplate.exchange(
                url, HttpMethod.POST, entity, XrayInferResponse.class);

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            throw new IllegalStateException("XrayGraphRAG inference 응답을 받지 못했습니다.");
        }

        XrayInferResponse xray = response.getBody();
        RadiologyAnalysisResponseDTO out = new RadiologyAnalysisResponseDTO();
        out.setHeatmapUrl(toAbsoluteUrl(xray.getHeatmapPath()));
        out.setWarning(xray.getWarning());
        out.setPredictedDiseases(toPredictedDiseases(xray.getPredictedDiseases()));
        return out;
    }

    private String normalizeView(String view) {
        String candidate = view == null || view.isBlank() ? defaultView : view;
        candidate = candidate == null || candidate.isBlank() ? "PA" : candidate.trim().toUpperCase();
        if (!"AP".equals(candidate) && !"PA".equals(candidate)) {
            log.warn("지원하지 않는 Xray view={} 요청, defaultView={} 사용", view, defaultView);
            return defaultView == null || defaultView.isBlank() ? "PA" : defaultView.trim().toUpperCase();
        }
        return candidate;
    }

    private String toAbsoluteUrl(String heatmapPath) {
        if (heatmapPath == null || heatmapPath.isBlank()) {
            return null;
        }
        if (heatmapPath.startsWith("http://") || heatmapPath.startsWith("https://")) {
            return heatmapPath;
        }
        String normalizedBase = publicBaseUrl.endsWith("/")
                ? publicBaseUrl.substring(0, publicBaseUrl.length() - 1)
                : publicBaseUrl;
        String normalizedPath = heatmapPath.startsWith("/") ? heatmapPath : "/" + heatmapPath;
        return normalizedBase + normalizedPath;
    }

    private List<RadiologyAnalysisResponseDTO.PredictedDisease> toPredictedDiseases(
            List<XrayPredictedDisease> diseases) {
        List<RadiologyAnalysisResponseDTO.PredictedDisease> out = new ArrayList<>();
        if (diseases == null) {
            return out;
        }
        for (XrayPredictedDisease disease : diseases) {
            if (disease == null
                    || disease.getDisease() == null
                    || EXCLUDED_DISEASE_TAGS.contains(disease.getDisease().toLowerCase())) {
                continue;
            }
            out.add(new RadiologyAnalysisResponseDTO.PredictedDisease(
                    disease.getDisease(),
                    disease.getScore(),
                    disease.getReason()));
        }
        out.sort((a, b) -> Double.compare(b.getScore(), a.getScore()));
        if (out.size() > MAX_PREDICTED_DISEASES) {
            return new ArrayList<>(out.subList(0, MAX_PREDICTED_DISEASES));
        }
        return out;
    }

    @Data
    public static class XrayInferResponse {
        private List<XrayPredictedDisease> predictedDiseases = new ArrayList<>();
        private String heatmapPath;
        private String warning;
    }

    @Data
    public static class XrayPredictedDisease {
        private String disease;
        private double score;
        private String reason;
    }
}
