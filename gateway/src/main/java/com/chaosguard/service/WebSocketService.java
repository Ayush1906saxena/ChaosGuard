package com.chaosguard.service;

import com.chaosguard.model.Scan;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class WebSocketService {

    private final SimpMessagingTemplate messagingTemplate;

    public void broadcastScanUpdate(Scan scan) {
        Map<String, Object> message = new HashMap<>();
        message.put("type", "SCAN_UPDATE");
        message.put("scanId", scan.getId().toString());
        message.put("status", scan.getStatus().name());
        message.put("repoUrl", scan.getRepoUrl());
        message.put("tier", scan.getTier().name());

        String destination = "/topic/scans/" + scan.getId();
        messagingTemplate.convertAndSend(destination, message);
        messagingTemplate.convertAndSend("/topic/scans", message);

        log.debug("Broadcast scan update for {} to {}", scan.getId(), destination);
    }

    public void broadcastProgress(String scanId, Map<String, Object> progress) {
        Map<String, Object> message = new HashMap<>(progress);
        message.put("type", "SCAN_PROGRESS");

        messagingTemplate.convertAndSend("/topic/scans/" + scanId + "/progress", message);
        log.debug("Broadcast progress for scan {}", scanId);
    }

    public void broadcastScanComplete(String scanId, Map<String, Object> result) {
        Map<String, Object> message = new HashMap<>(result);
        message.put("type", "SCAN_COMPLETE");

        messagingTemplate.convertAndSend("/topic/scans/" + scanId + "/complete", message);
        messagingTemplate.convertAndSend("/topic/scans/" + scanId, message);
        log.debug("Broadcast scan complete for {}", scanId);
    }

    public void broadcastResultsReady(String scanId, Map<String, Object> result) {
        Map<String, Object> message = new HashMap<>(result);
        message.put("type", "RESULTS_READY");

        messagingTemplate.convertAndSend("/topic/scans/" + scanId + "/results", message);
        log.debug("Broadcast results ready for scan {}", scanId);
    }

    public void broadcastError(String scanId, String error) {
        Map<String, Object> message = new HashMap<>();
        message.put("type", "ERROR");
        message.put("scanId", scanId);
        message.put("error", error);

        messagingTemplate.convertAndSend("/topic/scans/" + scanId + "/error", message);
        log.debug("Broadcast error for scan {}: {}", scanId, error);
    }
}
