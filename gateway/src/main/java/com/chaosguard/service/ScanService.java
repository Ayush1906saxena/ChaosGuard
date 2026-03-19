package com.chaosguard.service;

import com.chaosguard.model.Scan;
import com.chaosguard.model.Scan.ScanStatus;
import com.chaosguard.model.Scan.ScanTier;
import com.chaosguard.repository.ScanRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class ScanService {

    private final ScanRepository scanRepository;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final WebSocketService webSocketService;

    @Value("${chaosguard.kafka.topics.repo-clone-events}")
    private String repoCloneEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-recon-events}")
    private String scanReconEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-hunter-events}")
    private String scanHunterEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-siege-events}")
    private String scanSiegeEventsTopic;

    @Value("${chaosguard.scan.max-concurrent-scans}")
    private int maxConcurrentScans;

    @Transactional
    public Scan createScan(String repoUrl, String branch, ScanTier tier, String targetUrl) {
        validateRepoUrl(repoUrl);

        // LIVE tier requires a target URL
        if (tier == ScanTier.LIVE) {
            if (targetUrl == null || targetUrl.isBlank()) {
                throw new IllegalArgumentException("target_url is required for LIVE tier scans");
            }
            validateTargetUrl(targetUrl);
        }

        long activeScans = scanRepository.countActiveScans();
        if (activeScans >= maxConcurrentScans) {
            throw new IllegalStateException("Maximum concurrent scans limit reached: " + maxConcurrentScans);
        }

        if (branch == null || branch.isBlank()) {
            branch = "main";
        }

        Scan scan = Scan.builder()
                .repoUrl(repoUrl)
                .branch(branch)
                .tier(tier)
                .status(ScanStatus.QUEUED)
                .build();

        scan = scanRepository.save(scan);
        log.info("Created scan {} for repo {} branch {} tier {}", scan.getId(), repoUrl, branch, tier);

        Map<String, Object> cloneEvent = new HashMap<>();
        cloneEvent.put("scanId", scan.getId().toString());
        cloneEvent.put("repoUrl", repoUrl);
        cloneEvent.put("branch", branch);
        cloneEvent.put("tier", tier.name());
        cloneEvent.put("timestamp", Instant.now().toString());
        if (targetUrl != null && !targetUrl.isBlank()) {
            cloneEvent.put("targetUrl", targetUrl);
        }

        kafkaTemplate.send(repoCloneEventsTopic, scan.getId().toString(), cloneEvent);

        // Tier workers are triggered by the indexer after indexing completes
        // (indexer publishes to the tier-specific topic when done)

        log.info("Published clone event for scan {} to {}", scan.getId(), repoCloneEventsTopic);

        webSocketService.broadcastScanUpdate(scan);

        return scan;
    }

    public Scan getScan(UUID scanId) {
        return scanRepository.findById(scanId)
                .orElseThrow(() -> new NoSuchElementException("Scan not found: " + scanId));
    }

    @Transactional
    public Scan updateScanStatus(UUID scanId, ScanStatus status, String errorMessage) {
        Scan scan = getScan(scanId);
        scan.setStatus(status);

        if (errorMessage != null) {
            scan.setErrorMessage(errorMessage);
        }

        if (status == ScanStatus.COMPLETE || status == ScanStatus.FAILED) {
            scan.setCompletedAt(Instant.now());
        }

        scan = scanRepository.save(scan);
        log.info("Updated scan {} status to {}", scanId, status);

        webSocketService.broadcastScanUpdate(scan);

        return scan;
    }

    @Transactional
    public Scan updateScanMetadata(UUID scanId, Map<String, Object> metadata) {
        Scan scan = getScan(scanId);
        scan.setRepoMetadata(metadata);
        return scanRepository.save(scan);
    }

    @Transactional
    public Scan updateScanSummary(UUID scanId, Map<String, Object> summary) {
        Scan scan = getScan(scanId);
        scan.setSummary(summary);
        return scanRepository.save(scan);
    }

    public List<Scan> getActiveScans() {
        return scanRepository.findActiveScans();
    }

    public Map<String, Object> getEstimatedTime(ScanTier tier) {
        Map<String, Object> estimate = new HashMap<>();
        switch (tier) {
            case RECON -> {
                estimate.put("estimatedMinutes", 5);
                estimate.put("description", "Quick reconnaissance scan - surface-level vulnerability detection");
            }
            case HUNTER -> {
                estimate.put("estimatedMinutes", 15);
                estimate.put("description", "Deep vulnerability hunting with fix generation");
            }
            case SIEGE -> {
                estimate.put("estimatedMinutes", 30);
                estimate.put("description", "Full siege mode - attack chains, chaos scenarios, and pentest playbook");
            }
            case LIVE -> {
                estimate.put("estimatedMinutes", 35);
                estimate.put("description", "Full analysis plus dynamic application security testing against a live target");
            }
        }
        return estimate;
    }

    @Transactional
    public Scan createScan(String repoUrl, String branch, ScanTier tier) {
        return createScan(repoUrl, branch, tier, null);
    }

    private void validateTargetUrl(String targetUrl) {
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            throw new IllegalArgumentException("target_url must use http or https protocol");
        }
        String host = targetUrl.replaceFirst("https?://", "").split("[:/]")[0].toLowerCase();
        List<String> allowedPatterns = List.of(
            "localhost", "127.0.0.1", "0.0.0.0",
            "host.docker.internal", "172.17.", "10.0.", "192.168.",
            "staging", "dev", "test", "qa", "sandbox"
        );
        boolean allowed = allowedPatterns.stream().anyMatch(
            p -> host.equals(p) || host.contains(p + ".") || host.contains("." + p)
        );
        if (!allowed) {
            throw new IllegalArgumentException(
                "target_url must point to a staging, dev, test, or localhost environment. " +
                "Production targets are not allowed for safety."
            );
        }
    }

    private void validateRepoUrl(String repoUrl) {
        if (repoUrl == null || repoUrl.isBlank()) {
            throw new IllegalArgumentException("Repository URL cannot be empty");
        }
        if (!repoUrl.startsWith("https://") && !repoUrl.startsWith("http://") && !repoUrl.startsWith("git@")) {
            throw new IllegalArgumentException("Invalid repository URL format: " + repoUrl);
        }
        if (repoUrl.contains("..") || repoUrl.contains(";") || repoUrl.contains("|")) {
            throw new IllegalArgumentException("Repository URL contains invalid characters");
        }
    }
}
