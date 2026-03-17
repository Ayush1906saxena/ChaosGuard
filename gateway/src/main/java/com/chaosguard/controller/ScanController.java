package com.chaosguard.controller;

import com.chaosguard.model.AttackChain;
import com.chaosguard.model.ChaosScenario;
import com.chaosguard.model.Finding;
import com.chaosguard.model.FindingFeedback;
import com.chaosguard.model.FindingFeedback.FeedbackLabel;
import com.chaosguard.model.Scan;
import com.chaosguard.model.Scan.ScanTier;
import com.chaosguard.repository.AttackChainRepository;
import com.chaosguard.repository.ChaosScenarioRepository;
import com.chaosguard.repository.FindingRepository;
import com.chaosguard.repository.ScanRepository;
import com.chaosguard.service.FeedbackService;
import com.chaosguard.service.ScanService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@Slf4j
public class ScanController {

    private final ScanService scanService;
    private final ScanRepository scanRepository;
    private final FindingRepository findingRepository;
    private final AttackChainRepository attackChainRepository;
    private final ChaosScenarioRepository chaosScenarioRepository;
    private final com.chaosguard.repository.GeneratedFixRepository generatedFixRepository;
    private final FeedbackService feedbackService;

    @PostMapping("/scans")
    public ResponseEntity<Map<String, Object>> createScan(@RequestBody Map<String, String> request) {
        String repoUrl = request.get("repoUrl");
        String tierStr = request.get("tier");
        String branch = request.get("branch");
        String targetUrl = request.get("targetUrl");

        if (repoUrl == null || repoUrl.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "repoUrl is required"));
        }

        if (tierStr == null || tierStr.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "tier is required"));
        }

        ScanTier tier;
        try {
            tier = ScanTier.valueOf(tierStr.toUpperCase());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Invalid tier. Must be one of: RECON, HUNTER, SIEGE, LIVE"));
        }

        try {
            Scan scan = scanService.createScan(repoUrl, branch, tier, targetUrl);
            Map<String, Object> estimate = scanService.getEstimatedTime(tier);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("id", scan.getId().toString());
            response.put("repoUrl", scan.getRepoUrl());
            response.put("branch", scan.getBranch());
            response.put("tier", scan.getTier().name());
            response.put("status", scan.getStatus().name());
            response.put("createdAt", scan.getCreatedAt());
            response.put("updatedAt", scan.getUpdatedAt());
            response.put("estimatedMinutes", estimate.get("estimatedMinutes"));

            return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
        } catch (IllegalStateException e) {
            return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                    .body(Map.of("error", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/scans/{scanId}")
    public ResponseEntity<?> getScan(@PathVariable UUID scanId) {
        try {
            Scan scan = scanService.getScan(scanId);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("id", scan.getId().toString());
            response.put("repoUrl", scan.getRepoUrl());
            response.put("branch", scan.getBranch());
            response.put("tier", scan.getTier().name());
            response.put("status", scan.getStatus().name());
            response.put("repoMetadata", scan.getRepoMetadata());
            response.put("summary", scan.getSummary());
            response.put("errorMessage", scan.getErrorMessage());
            response.put("createdAt", scan.getCreatedAt());
            response.put("updatedAt", scan.getUpdatedAt());
            response.put("completedAt", scan.getCompletedAt());

            return ResponseEntity.ok(response);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/scans/{scanId}/findings")
    public ResponseEntity<?> getFindings(
            @PathVariable UUID scanId,
            @RequestParam(required = false) String severity,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String tier,
            @RequestParam(required = false) String agent,
            @RequestParam(required = false) Double minConfidence,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "cvssScore"));
        Page<Finding> findings = findingRepository.findWithFilters(
                scanId, severity, category, null, pageable);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("content", findings.getContent());
        response.put("page", findings.getNumber());
        response.put("size", findings.getSize());
        response.put("totalElements", findings.getTotalElements());
        response.put("totalPages", findings.getTotalPages());

        return ResponseEntity.ok(response);
    }

    @GetMapping("/scans/{scanId}/attack-chains")
    public ResponseEntity<?> getAttackChains(@PathVariable UUID scanId) {
        Scan scan;
        try {
            scan = scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        if (scan.getTier() != ScanTier.SIEGE) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Attack chains are only available for SIEGE tier scans"));
        }

        List<AttackChain> chains = attackChainRepository.findByScanIdOrderBySeverityAsc(scanId);
        return ResponseEntity.ok(chains);
    }

    @GetMapping("/scans/{scanId}/chaos-scenarios")
    public ResponseEntity<?> getChaosScenarios(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        List<ChaosScenario> scenarios = chaosScenarioRepository.findByScanId(scanId);
        return ResponseEntity.ok(scenarios);
    }

    @GetMapping("/scans/{scanId}/report")
    public ResponseEntity<?> getReport(
            @PathVariable UUID scanId,
            @RequestParam(defaultValue = "json") String format) {
        Scan scan;
        try {
            scan = scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        List<Finding> findings = findingRepository.findByScanIdOrderBySeverity(scanId);
        List<ChaosScenario> scenarios = chaosScenarioRepository.findByScanId(scanId);
        List<Object[]> severityCounts = findingRepository.countBySeverityForScan(scanId);

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("scan", scan);
        report.put("findings", findings);
        report.put("chaosScenarios", scenarios);

        Map<String, Long> severityBreakdown = new LinkedHashMap<>();
        for (Object[] row : severityCounts) {
            severityBreakdown.put((String) row[0], (Long) row[1]);
        }
        report.put("severityBreakdown", severityBreakdown);

        if (scan.getTier() == ScanTier.SIEGE) {
            List<AttackChain> chains = attackChainRepository.findByScanIdOrderBySeverityAsc(scanId);
            report.put("attackChains", chains);
        }

        report.put("format", format);
        report.put("generatedAt", Instant.now());

        return ResponseEntity.ok(report);
    }

    @GetMapping("/scans/{scanId}/pentest-playbook")
    public ResponseEntity<?> getPentestPlaybook(@PathVariable UUID scanId) {
        Scan scan;
        try {
            scan = scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        if (scan.getTier() != ScanTier.SIEGE) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Pentest playbook is only available for SIEGE tier scans"));
        }

        List<Finding> findings = findingRepository.findByScanIdOrderBySeverity(scanId);
        List<AttackChain> chains = attackChainRepository.findByScanIdOrderBySeverityAsc(scanId);
        List<ChaosScenario> scenarios = chaosScenarioRepository.findByScanId(scanId);

        Map<String, Object> playbook = new LinkedHashMap<>();
        playbook.put("scanId", scanId.toString());
        playbook.put("repoUrl", scan.getRepoUrl());
        playbook.put("generatedAt", Instant.now());
        playbook.put("findings", findings);
        playbook.put("attackChains", chains);
        playbook.put("chaosScenarios", scenarios);
        playbook.put("summary", scan.getSummary());

        return ResponseEntity.ok(playbook);
    }

    // ── Fixes ────────────────────────────────────────────────────────────────────

    @GetMapping("/scans/{scanId}/fixes")
    public ResponseEntity<?> getFixes(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
        List<com.chaosguard.model.GeneratedFix> fixes = generatedFixRepository.findByScanId(scanId);
        return ResponseEntity.ok(fixes);
    }

    @GetMapping("/scans/{scanId}/fixes/{fixId}")
    public ResponseEntity<?> getFix(@PathVariable UUID scanId, @PathVariable UUID fixId) {
        return generatedFixRepository.findById(fixId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Fix not found")));
    }

    // ── Playbooks ───────────────────────────────────────────────────────────────

    @GetMapping("/scans/{scanId}/playbooks")
    public ResponseEntity<?> getPlaybooks(@PathVariable UUID scanId) {
        Scan scan;
        try {
            scan = scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
        if (scan.getTier() != ScanTier.SIEGE) {
            return ResponseEntity.ok(List.of());
        }
        List<Finding> findings = findingRepository.findByScanIdOrderBySeverity(scanId);
        List<AttackChain> chains = attackChainRepository.findByScanIdOrderBySeverityAsc(scanId);
        List<ChaosScenario> scenarios = chaosScenarioRepository.findByScanId(scanId);
        Map<String, Object> playbook = new LinkedHashMap<>();
        playbook.put("id", scanId.toString());
        playbook.put("scanId", scanId.toString());
        playbook.put("repoUrl", scan.getRepoUrl());
        playbook.put("generatedAt", Instant.now());
        playbook.put("findings", findings);
        playbook.put("attackChains", chains);
        playbook.put("chaosScenarios", scenarios);
        playbook.put("summary", scan.getSummary());
        return ResponseEntity.ok(List.of(playbook));
    }

    // ── Code Explorer ───────────────────────────────────────────────────────────

    @GetMapping("/scans/{scanId}/files")
    public ResponseEntity<?> getFiles(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
        // Return file tree from repo metadata
        Scan scan = scanService.getScan(scanId);
        if (scan.getRepoMetadata() == null) {
            return ResponseEntity.ok(List.of());
        }
        return ResponseEntity.ok(List.of());
    }

    @GetMapping("/scans/{scanId}/files/content")
    public ResponseEntity<?> getFileContent(@PathVariable UUID scanId, @RequestParam String path) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
        return ResponseEntity.ok(Map.of("path", path, "content", "", "language", ""));
    }

    // ── Dependency Graph ────────────────────────────────────────────────────────

    @GetMapping("/scans/{scanId}/dependency-graph")
    public ResponseEntity<?> getDependencyGraph(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }
        return ResponseEntity.ok(Map.of("nodes", List.of(), "edges", List.of()));
    }

    @PostMapping("/scans/{scanId}/search")
    public ResponseEntity<?> ragCodeSearch(
            @PathVariable UUID scanId,
            @RequestBody Map<String, String> request) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        String query = request.get("query");
        String language = request.get("language");

        if (query == null || query.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "query is required"));
        }

        List<Finding> findings = findingRepository.findByScanId(scanId);

        List<Finding> matched = findings.stream()
                .filter(f -> {
                    String searchText = (f.getTitle() + " " + f.getDescription() + " " +
                            f.getVulnerabilityType() + " " + f.getFilePath()).toLowerCase();
                    return searchText.contains(query.toLowerCase());
                })
                .filter(f -> language == null || language.isBlank() ||
                        f.getFilePath().toLowerCase().endsWith("." + language.toLowerCase()))
                .toList();

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("query", query);
        response.put("language", language);
        response.put("results", matched);
        response.put("totalResults", matched.size());

        return ResponseEntity.ok(response);
    }

    @GetMapping("/scans/queue-status")
    public ResponseEntity<?> getQueueStatus() {
        List<Object[]> rows = scanRepository.countByStatusAndTier();
        Map<String, Map<String, Long>> result = new LinkedHashMap<>();
        for (String tier : List.of("RECON", "HUNTER", "SIEGE", "LIVE")) {
            result.put(tier, new LinkedHashMap<>(Map.of("queued", 0L, "processing", 0L)));
        }
        for (Object[] row : rows) {
            String tier = row[0].toString();
            String status = row[1].toString();
            Long count = (Long) row[2];
            Map<String, Long> tierMap = result.computeIfAbsent(tier, k -> new LinkedHashMap<>());
            if ("QUEUED".equals(status)) {
                tierMap.merge("queued", count, Long::sum);
            } else {
                tierMap.merge("processing", count, Long::sum);
            }
        }
        return ResponseEntity.ok(result);
    }

    @GetMapping("/scans")
    public ResponseEntity<?> listScans(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Instant since = Instant.now().minus(30, ChronoUnit.DAYS);
        Page<Scan> scans = scanRepository.findRecentScans(since, pageable);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("content", scans.getContent());
        response.put("page", scans.getNumber());
        response.put("size", scans.getSize());
        response.put("totalElements", scans.getTotalElements());
        response.put("totalPages", scans.getTotalPages());

        return ResponseEntity.ok(response);
    }

    // ── Feedback Endpoints (Task 3) ────────────────────────────────────────────

    @PostMapping("/findings/{findingId}/feedback")
    public ResponseEntity<?> submitFeedback(
            @PathVariable UUID findingId,
            @RequestBody Map<String, String> request) {
        String labelStr = request.get("label");
        String comment = request.get("comment");

        if (labelStr == null || labelStr.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "label is required (TRUE_POSITIVE, FALSE_POSITIVE, WONT_FIX)"));
        }

        FeedbackLabel label;
        try {
            label = FeedbackLabel.valueOf(labelStr.toUpperCase());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Invalid label. Must be one of: TRUE_POSITIVE, FALSE_POSITIVE, WONT_FIX"));
        }

        try {
            FindingFeedback feedback = feedbackService.submitFeedback(findingId, label, comment);
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("id", feedback.getId().toString());
            response.put("findingId", findingId.toString());
            response.put("label", feedback.getLabel().name());
            response.put("codeFingerprint", feedback.getCodeFingerprint());
            response.put("createdAt", feedback.getCreatedAt());
            return ResponseEntity.status(HttpStatus.CREATED).body(response);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/findings/{findingId}/feedback")
    public ResponseEntity<?> getFeedback(@PathVariable UUID findingId) {
        List<FindingFeedback> feedbackList = feedbackService.getFeedback(findingId);
        return ResponseEntity.ok(Map.of("feedback", feedbackList));
    }

    // ── Metrics Endpoint (Task 6) ──────────────────────────────────────────────

    @GetMapping("/scans/{scanId}/metrics")
    public ResponseEntity<?> getScanMetrics(@PathVariable UUID scanId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
        }

        // Fetch metrics from Redis
        try {
            org.springframework.data.redis.core.RedisTemplate<String, String> redisTemplate = null;
            // Return basic metrics from scan data
            Scan scan = scanService.getScan(scanId);
            Map<String, Object> metrics = new LinkedHashMap<>();
            metrics.put("scanId", scanId.toString());
            metrics.put("tier", scan.getTier().name());
            metrics.put("status", scan.getStatus().name());
            metrics.put("createdAt", scan.getCreatedAt());
            metrics.put("completedAt", scan.getCompletedAt());
            if (scan.getCreatedAt() != null && scan.getCompletedAt() != null) {
                long durationMs = scan.getCompletedAt().toEpochMilli() - scan.getCreatedAt().toEpochMilli();
                metrics.put("durationSeconds", durationMs / 1000.0);
            }
            metrics.put("summary", scan.getSummary());
            return ResponseEntity.ok(metrics);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to retrieve metrics: " + e.getMessage()));
        }
    }
}
