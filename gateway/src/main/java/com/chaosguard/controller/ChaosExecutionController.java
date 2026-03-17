package com.chaosguard.controller;

import com.chaosguard.model.ChaosExperiment;
import com.chaosguard.model.ChaosScenario;
import com.chaosguard.model.Scan;
import com.chaosguard.repository.ChaosExperimentRepository;
import com.chaosguard.repository.ChaosScenarioRepository;
import com.chaosguard.service.ScanService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.*;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@Slf4j
public class ChaosExecutionController {

    private final ScanService scanService;
    private final ChaosScenarioRepository chaosScenarioRepository;
    private final ChaosExperimentRepository chaosExperimentRepository;
    private final StringRedisTemplate redisTemplate;

    @Value("${chaosguard.agents.url:http://agents:8082}")
    private String agentsUrl;

    /**
     * Start a chaos experiment for a specific scenario.
     */
    @PostMapping("/scans/{scanId}/chaos-experiments")
    public ResponseEntity<?> createExperiment(
            @PathVariable UUID scanId,
            @RequestBody Map<String, Object> request) {
        Scan scan;
        try {
            scan = scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        String scenarioId = (String) request.get("scenarioId");
        Boolean autoApprove = (Boolean) request.getOrDefault("autoApprove", false);

        // Build scenario data
        Map<String, Object> scenarioData = new LinkedHashMap<>();
        if (scenarioId != null) {
            try {
                UUID scenarioUuid = UUID.fromString(scenarioId);
                ChaosScenario scenario = chaosScenarioRepository.findById(scenarioUuid).orElse(null);
                if (scenario != null) {
                    scenarioData.put("id", scenario.getId().toString());
                    scenarioData.put("title", scenario.getTitle());
                    scenarioData.put("description", scenario.getDescription());
                    scenarioData.put("scenario_type", scenario.getScenarioType());
                    scenarioData.put("target_component", scenario.getTargetComponent());
                    scenarioData.put("injection_points", scenario.getInjectionPoints());
                    scenarioData.put("blast_radius", scenario.getBlastRadius());
                    scenarioData.put("expected_impact", scenario.getExpectedImpact());
                }
            } catch (IllegalArgumentException e) {
                // Not a valid UUID — use inline scenario data
                scenarioData = request;
            }
        } else {
            scenarioData = request;
        }

        // Determine clone path from scan metadata
        String clonePath = "/tmp/chaosguard/repos/" + scanId;

        // Call the agents service to start the experiment
        try {
            RestTemplate restTemplate = new RestTemplate();
            Map<String, Object> agentRequest = new LinkedHashMap<>();
            agentRequest.put("scan_id", scanId.toString());
            agentRequest.put("scenario", scenarioData);
            agentRequest.put("clone_path", clonePath);
            agentRequest.put("auto_approve", autoApprove);

            Map<?, ?> agentResponse = restTemplate.postForObject(
                    agentsUrl + "/chaos/execute", agentRequest, Map.class);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("scanId", scanId.toString());
            response.put("scenarioId", scenarioId);
            response.put("status", "STARTED");
            response.put("message", "Chaos experiment initiated. Poll for status updates.");

            return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);

        } catch (Exception e) {
            log.error("Failed to start chaos experiment for scan {}: {}", scanId, e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to start chaos experiment: " + e.getMessage()));
        }
    }

    /**
     * Approve a pending chaos experiment.
     */
    @PostMapping("/chaos-experiments/{experimentId}/approve")
    public ResponseEntity<?> approveExperiment(@PathVariable String experimentId) {
        redisTemplate.opsForValue().set(
                "chaos:approval:" + experimentId, "approved", 600, TimeUnit.SECONDS);
        return ResponseEntity.ok(Map.of("status", "approved", "experimentId", experimentId));
    }

    /**
     * Reject a pending chaos experiment.
     */
    @PostMapping("/chaos-experiments/{experimentId}/reject")
    public ResponseEntity<?> rejectExperiment(@PathVariable String experimentId) {
        redisTemplate.opsForValue().set(
                "chaos:approval:" + experimentId, "rejected", 600, TimeUnit.SECONDS);
        return ResponseEntity.ok(Map.of("status", "rejected", "experimentId", experimentId));
    }

    /**
     * Emergency stop — immediately abort all chaos for a scan.
     */
    @PostMapping("/scans/{scanId}/chaos-experiments/abort")
    public ResponseEntity<?> abortExperiments(@PathVariable UUID scanId) {
        redisTemplate.opsForValue().set(
                "chaos:kill:" + scanId, "1", 600, TimeUnit.SECONDS);
        log.warn("EMERGENCY STOP triggered for scan {}", scanId);
        return ResponseEntity.ok(Map.of(
                "status", "abort_triggered",
                "scanId", scanId.toString(),
                "message", "Emergency stop signal sent. All faults will be rolled back."));
    }

    /**
     * List all chaos experiments for a scan.
     */
    @GetMapping("/scans/{scanId}/chaos-experiments")
    public ResponseEntity<?> getExperiments(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        List<ChaosExperiment> experiments =
                chaosExperimentRepository.findByScanIdOrderByCreatedAtDesc(scanId);
        return ResponseEntity.ok(experiments);
    }

    /**
     * Get a single chaos experiment by ID.
     */
    @GetMapping("/chaos-experiments/{experimentId}")
    public ResponseEntity<?> getExperiment(@PathVariable UUID experimentId) {
        return chaosExperimentRepository.findById(experimentId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElse(ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "Experiment not found")));
    }

    /**
     * Check if a repo has a docker-compose file (determines if chaos execution is available).
     */
    @GetMapping("/scans/{scanId}/chaos-availability")
    public ResponseEntity<?> checkChaosAvailability(@PathVariable UUID scanId) {
        String clonePath = "/tmp/chaosguard/repos/" + scanId;
        java.io.File composeFile = new java.io.File(clonePath, "docker-compose.yml");
        if (!composeFile.exists()) {
            composeFile = new java.io.File(clonePath, "docker-compose.yaml");
        }
        if (!composeFile.exists()) {
            composeFile = new java.io.File(clonePath, "compose.yml");
        }

        boolean available = composeFile.exists();

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("available", available);
        response.put("reason", available
                ? "docker-compose.yml detected in repository"
                : "No docker-compose.yml found — chaos execution requires a runnable Docker Compose application");

        return ResponseEntity.ok(response);
    }
}
