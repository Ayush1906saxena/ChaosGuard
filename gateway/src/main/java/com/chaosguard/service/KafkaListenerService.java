package com.chaosguard.service;

import com.chaosguard.model.Scan.ScanStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class KafkaListenerService {

    private final ScanService scanService;
    private final WebSocketService webSocketService;

    @KafkaListener(topics = "${chaosguard.kafka.topics.scan-progress}",
                   groupId = "chaosguard-gateway")
    public void handleScanProgress(@Payload Map<String, Object> event, Acknowledgment ack) {
        try {
            String scanId = (String) event.get("scanId");
            String status = (String) event.get("status");
            String message = (String) event.get("message");
            Object progressObj = event.get("progress");
            Integer progress = progressObj != null ? ((Number) progressObj).intValue() : null;

            log.info("Scan progress for {}: status={}, message={}, progress={}",
                    scanId, status, message, progress);

            UUID scanUuid = UUID.fromString(scanId);

            if (status != null) {
                try {
                    ScanStatus scanStatus = ScanStatus.valueOf(status);
                    scanService.updateScanStatus(scanUuid, scanStatus, null);
                } catch (IllegalArgumentException e) {
                    log.warn("Unknown scan status: {}", status);
                }
            }

            webSocketService.broadcastProgress(scanId, Map.of(
                    "scanId", scanId,
                    "status", status != null ? status : "UNKNOWN",
                    "message", message != null ? message : "",
                    "progress", progress != null ? progress : 0
            ));

            ack.acknowledge();

        } catch (Exception e) {
            log.error("Error handling scan progress event: {}", e.getMessage(), e);
            ack.acknowledge();
        }
    }

    @KafkaListener(topics = "${chaosguard.kafka.topics.scan-complete}",
                   groupId = "chaosguard-gateway")
    public void handleScanComplete(@Payload Map<String, Object> event, Acknowledgment ack) {
        try {
            String scanId = event.get("scanId") != null ? event.get("scanId").toString() : null;
            String status = event.get("status") != null ? event.get("status").toString() : null;
            String errorMessage = (String) event.get("errorMessage");

            if (scanId == null || scanId.isBlank()) {
                log.warn("Ignoring scan-complete event with null scanId: {}", event);
                ack.acknowledge();
                return;
            }

            log.info("Scan complete for {}: status={}", scanId, status);

            UUID scanUuid = UUID.fromString(scanId);

            ScanStatus scanStatus = "FAILED".equals(status) ? ScanStatus.FAILED : ScanStatus.COMPLETE;
            scanService.updateScanStatus(scanUuid, scanStatus, errorMessage);

            @SuppressWarnings("unchecked")
            Map<String, Object> summary = (Map<String, Object>) event.get("summary");
            if (summary != null) {
                scanService.updateScanSummary(scanUuid, summary);
            }

            webSocketService.broadcastScanComplete(scanId, Map.of(
                    "scanId", scanId,
                    "status", scanStatus.name(),
                    "summary", summary != null ? summary : Map.of()
            ));

            ack.acknowledge();

        } catch (Exception e) {
            log.error("Error handling scan complete event: {}", e.getMessage(), e);
            ack.acknowledge();
        }
    }

    @KafkaListener(topics = "${chaosguard.kafka.topics.results-ready}",
                   groupId = "chaosguard-gateway")
    public void handleResultsReady(@Payload Map<String, Object> event, Acknowledgment ack) {
        try {
            String scanId = (String) event.get("scanId");
            String resultType = (String) event.get("resultType");
            Object countObj = event.get("count");
            Integer count = countObj != null ? ((Number) countObj).intValue() : 0;

            log.info("Results ready for scan {}: type={}, count={}", scanId, resultType, count);

            webSocketService.broadcastResultsReady(scanId, Map.of(
                    "scanId", scanId,
                    "resultType", resultType != null ? resultType : "unknown",
                    "count", count
            ));

            ack.acknowledge();

        } catch (Exception e) {
            log.error("Error handling results ready event: {}", e.getMessage(), e);
            ack.acknowledge();
        }
    }
}
