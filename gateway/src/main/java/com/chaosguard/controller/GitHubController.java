package com.chaosguard.controller;

import com.chaosguard.model.GeneratedFix;
import com.chaosguard.repository.GeneratedFixRepository;
import com.chaosguard.service.GitHubService;
import com.chaosguard.service.ScanService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.*;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@Slf4j
public class GitHubController {

    private final GitHubService gitHubService;
    private final ScanService scanService;
    private final GeneratedFixRepository generatedFixRepository;

    @PostMapping({"/scans/{scanId}/github/issues", "/scans/{scanId}/fixes/{fixId}/create-issue"})
    public ResponseEntity<?> createIssues(
            @PathVariable UUID scanId,
            @PathVariable(required = false) UUID fixId,
            @RequestBody(required = false) Map<String, String> request) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        try {
            // Single-finding issue creation when fixId is provided
            if (fixId != null) {
                GeneratedFix fix = generatedFixRepository.findById(fixId)
                        .orElseThrow(() -> new NoSuchElementException("Fix not found: " + fixId));
                Map<String, Object> result = gitHubService.createSingleIssue(scanId, fix.getFindingId());
                return ResponseEntity.status(HttpStatus.CREATED).body(result);
            }

            // Bulk issue creation
            List<Map<String, Object>> createdIssues = gitHubService.createIssues(scanId);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("scanId", scanId.toString());
            response.put("issuesCreated", createdIssues.size());
            response.put("issues", createdIssues);

            return ResponseEntity.status(HttpStatus.CREATED).body(response);
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "GitHub token is not configured. Provide a valid token."));
        } catch (IOException e) {
            log.error("Failed to create GitHub issues for scan {}: {}", scanId, e.getMessage());

            String message = e.getMessage();
            if (message != null && message.contains("rate limit")) {
                return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                        .body(Map.of("error", "GitHub API rate limit exceeded. Please try again later."));
            }
            if (message != null && message.contains("Not Found")) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "GitHub repository not found. Check the repo URL and token permissions."));
            }

            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to create GitHub issues: " + message));
        }
    }

    @PostMapping("/scans/{scanId}/fixes/{fixId}/create-pr")
    public ResponseEntity<?> createSingleFixPR(
            @PathVariable UUID scanId,
            @PathVariable UUID fixId) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        try {
            Map<String, Object> result = gitHubService.createSinglePullRequest(scanId, fixId);
            return ResponseEntity.status(HttpStatus.CREATED).body(result);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "GitHub token is not configured. Provide a valid token."));
        } catch (IOException e) {
            log.error("Failed to create fix PR for scan {} fix {}: {}", scanId, fixId, e.getMessage());

            String message = e.getMessage();
            if (message != null && message.contains("rate limit")) {
                return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                        .body(Map.of("error", "GitHub API rate limit exceeded. Please try again later."));
            }
            if (message != null && message.contains("Not Found")) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "GitHub repository not found. Check the repo URL and token permissions."));
            }

            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to create fix pull request: " + message));
        }
    }

    @PostMapping({"/scans/{scanId}/github/fixes", "/scans/{scanId}/fixes/create-pr"})
    public ResponseEntity<?> createFixes(
            @PathVariable UUID scanId,
            @RequestBody(required = false) Map<String, Object> request) {
        try {
            scanService.getScan(scanId);
        } catch (NoSuchElementException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage()));
        }

        try {
            List<Map<String, Object>> createdPRs = gitHubService.createPullRequests(scanId);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("scanId", scanId.toString());
            response.put("pullRequestsCreated", createdPRs.size());
            response.put("pullRequests", createdPRs);

            return ResponseEntity.status(HttpStatus.CREATED).body(response);
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "GitHub token is not configured. Provide a valid token."));
        } catch (IOException e) {
            log.error("Failed to create fix PRs for scan {}: {}", scanId, e.getMessage());

            String message = e.getMessage();
            if (message != null && message.contains("rate limit")) {
                return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                        .body(Map.of("error", "GitHub API rate limit exceeded. Please try again later."));
            }
            if (message != null && message.contains("Not Found")) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "GitHub repository not found. Check the repo URL and token permissions."));
            }

            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to create fix pull requests: " + message));
        }
    }
}
