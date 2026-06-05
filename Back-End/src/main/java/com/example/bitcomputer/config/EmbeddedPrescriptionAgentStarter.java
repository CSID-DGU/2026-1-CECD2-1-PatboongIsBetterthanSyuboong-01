package com.example.bitcomputer.config;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/**
 * 로컬 개발 편의: Spring 기동 시 같은 호스트에서 {@code uvicorn prescription_api:app} 을
 * 자식 프로세스로 실행합니다. 프로덕션에서는 끄고(기본값) 컨테이너/프로세스 매니저로 운영하세요.
 */
@Component
@ConditionalOnProperty(prefix = "ai.prescription-agent.embed", name = "enabled", havingValue = "true")
@Order(-100)
public class EmbeddedPrescriptionAgentStarter implements ApplicationRunner, DisposableBean {

    private static final Logger log = LoggerFactory.getLogger(EmbeddedPrescriptionAgentStarter.class);

    private final RestTemplate restTemplate;

    @Value("${ai.prescription-agent.base-url:http://localhost:8001}")
    private String prescriptionAgentBaseUrl;

    @Value("${ai.prescription-agent.embed.working-directory:../GraphDB/langchain_graph_qa}")
    private String embedWorkingDirectory;

    @Value("${ai.prescription-agent.embed.python-command:python3}")
    private String embedPythonCommand;

    @Value("${ai.prescription-agent.embed.host:0.0.0.0}")
    private String embedHost;

    @Value("${ai.prescription-agent.embed.skip-if-healthy:true}")
    private boolean embedSkipIfHealthy;

    @Value("${ai.prescription-agent.embed.startup-timeout-ms:90000}")
    private long embedStartupTimeoutMs;

    @Value("${gemini.api.key:}")
    private String geminiApiKey;

    private volatile Process ownedProcess;

    public EmbeddedPrescriptionAgentStarter(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        String healthUrl = healthEndpointUrl();
        if (embedSkipIfHealthy && isReachable(healthUrl)) {
            log.info("prescription_api 가 이미 응답 중입니다 ({}) — embed 를 건너뜁니다.", healthUrl);
            return;
        }

        Path workDir = resolveWorkingDirectory();
        Path entry = workDir.resolve("prescription_api.py");
        if (!Files.isRegularFile(entry)) {
            throw new IllegalStateException(
                    "prescription_api.py 를 찾을 수 없습니다: " + entry
                            + " — ai.prescription-agent.embed.working-directory 를 확인하세요.");
        }

        int port = extractPortFromBaseUrl();
        String pythonExe = resolvePythonExecutable(workDir);
        String configuredRaw = embedPythonCommand == null ? "" : embedPythonCommand.trim();
        if (!pythonExe.equals(configuredRaw.isEmpty() ? "python3" : configuredRaw)) {
            log.info("prescription_api 용 Python: 설정값 대신 사용 가능한 경로를 선택했습니다 — {}", pythonExe);
        }

        List<String> command = new ArrayList<>();
        command.add(pythonExe);
        command.add("-m");
        command.add("uvicorn");
        command.add("prescription_api:app");
        command.add("--host");
        command.add(embedHost);
        command.add("--port");
        command.add(Integer.toString(port));

        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(workDir.toFile());
        pb.inheritIO();

        String googleKey = resolveGoogleApiKey();
        if (googleKey != null && !googleKey.isBlank()) {
            pb.environment().put("GOOGLE_API_KEY", googleKey);
        } else {
            log.warn(
                    "GOOGLE_API_KEY 를 설정하지 못했습니다(gemini.api.key 및 환경변수 비어 있음). "
                            + "처방 API 호출은 실패할 수 있습니다.");
        }

        log.info("prescription_api 자식 프로세스 시작: {} (cwd={})", String.join(" ", command), workDir);
        ownedProcess = pb.start();

        long deadline = System.currentTimeMillis() + embedStartupTimeoutMs;
        Exception last = null;
        while (System.currentTimeMillis() < deadline) {
            if (!ownedProcess.isAlive()) {
                int exit = ownedProcess.exitValue();
                throw new IllegalStateException(
                        "prescription_api 프로세스가 곧바로 종료되었습니다 (exitCode=" + exit + "). "
                                + "사용한 Python: " + pythonExe
                                + " — uvicorn 모듈이 없으면 프로젝트 루트에서 "
                                + "\"pip install -r GraphDB/langchain_graph_qa/requirements.txt\" 로 .venv 를 채우거나, "
                                + "ai.prescription-agent.embed.python-command 에 해당 venv 의 python 경로를 지정하세요.");
            }
            try {
                if (isReachable(healthUrl)) {
                    log.info("prescription_api 준비 완료 ({})", healthUrl);
                    return;
                }
            } catch (Exception e) {
                last = e;
            }
            Thread.sleep(400);
        }
        String msg = "prescription_api 가 " + embedStartupTimeoutMs + "ms 안에 /health 에 응답하지 않았습니다: " + healthUrl;
        if (last != null) {
            throw new IllegalStateException(msg, last);
        }
        throw new IllegalStateException(msg);
    }

    /**
     * PATH 의 {@code python3}(예: Anaconda)에 uvicorn 이 없는 경우가 많아,
     * 설정값이 단순 명령어면 프로젝트 루트 {@code .venv} 를 우선 시도합니다.
     */
    private String resolvePythonExecutable(Path workDir) {
        String configured = embedPythonCommand == null ? "python3" : embedPythonCommand.trim();
        if (configured.isEmpty()) {
            configured = "python3";
        }

        if (configured.contains("/") || configured.contains("\\")) {
            Path p = Paths.get(configured);
            if (!p.isAbsolute()) {
                p = Paths.get(System.getProperty("user.dir")).resolve(p).normalize();
            }
            if (isRunnablePython(p)) {
                return p.toString();
            }
        }

        Path repoRoot = workDir.getParent() != null && workDir.getParent().getParent() != null
                ? workDir.getParent().getParent()
                : null;
        if (repoRoot != null) {
            for (Path candidate : Arrays.asList(
                    repoRoot.resolve(".venv/bin/python"),
                    repoRoot.resolve(".venv/Scripts/python.exe"))) {
                if (isRunnablePython(candidate)) {
                    return candidate.normalize().toString();
                }
            }
        }

        Path cwd = Paths.get(System.getProperty("user.dir"));
        for (Path rel : Arrays.asList(
                cwd.resolve("../.venv/bin/python"),
                cwd.resolve("../../.venv/bin/python"),
                cwd.resolve("../.venv/Scripts/python.exe"),
                cwd.resolve("../../.venv/Scripts/python.exe"))) {
            Path norm = rel.normalize();
            if (isRunnablePython(norm)) {
                return norm.toString();
            }
        }

        return configured;
    }

    private static boolean isRunnablePython(Path p) {
        return Files.isRegularFile(p) && Files.isExecutable(p);
    }

    private String resolveGoogleApiKey() {
        String env = System.getenv("GOOGLE_API_KEY");
        if (env != null && !env.isBlank()) {
            return env;
        }
        return geminiApiKey;
    }

    private Path resolveWorkingDirectory() {
        Path p = Paths.get(embedWorkingDirectory.trim());
        if (!p.isAbsolute()) {
            p = Paths.get(System.getProperty("user.dir")).resolve(p).normalize();
        }
        if (!Files.isDirectory(p)) {
            throw new IllegalStateException(
                    "유효한 디렉터리가 아닙니다: " + p + " — 백엔드를 프로젝트 Back-End 폴더에서 실행했는지 확인하세요.");
        }
        return p;
    }

    private int extractPortFromBaseUrl() {
        try {
            URI uri = URI.create(prescriptionAgentBaseUrl.trim());
            int port = uri.getPort();
            if (port > 0) {
                return port;
            }
            if ("https".equalsIgnoreCase(uri.getScheme())) {
                return 443;
            }
            return 80;
        } catch (Exception e) {
            throw new IllegalStateException("ai.prescription-agent.base-url 파싱 실패: " + prescriptionAgentBaseUrl, e);
        }
    }

    private String healthEndpointUrl() {
        String base = prescriptionAgentBaseUrl.trim();
        if (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base + "/health";
    }

    private boolean isReachable(String url) {
        try {
            var response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (RestClientException e) {
            return false;
        }
    }

    @Override
    public void destroy() {
        Process p = ownedProcess;
        if (p == null || !p.isAlive()) {
            return;
        }
        log.info("prescription_api 자식 프로세스 종료 중 (pid={})...", p.pid());
        p.destroy();
        try {
            if (!p.waitFor(5, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                p.waitFor(5, TimeUnit.SECONDS);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            p.destroyForcibly();
        }
    }
}
