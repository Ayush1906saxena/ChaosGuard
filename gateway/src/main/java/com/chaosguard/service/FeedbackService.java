package com.chaosguard.service;

import com.chaosguard.model.Finding;
import com.chaosguard.model.FindingFeedback;
import com.chaosguard.model.FindingFeedback.FeedbackLabel;
import com.chaosguard.repository.FindingFeedbackRepository;
import com.chaosguard.repository.FindingRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class FeedbackService {

    private final FindingFeedbackRepository feedbackRepository;
    private final FindingRepository findingRepository;

    @Transactional
    public FindingFeedback submitFeedback(UUID findingId, FeedbackLabel label, String comment) {
        Finding finding = findingRepository.findById(findingId)
                .orElseThrow(() -> new NoSuchElementException("Finding not found: " + findingId));

        String fingerprint = generateFingerprint(finding);

        FindingFeedback feedback = FindingFeedback.builder()
                .findingId(findingId)
                .label(label)
                .userComment(comment)
                .codeFingerprint(fingerprint)
                .build();

        feedback = feedbackRepository.save(feedback);
        log.info("Submitted {} feedback for finding {} (fingerprint: {})", label, findingId, fingerprint);

        return feedback;
    }

    public List<FindingFeedback> getFeedback(UUID findingId) {
        return feedbackRepository.findByFindingId(findingId);
    }

    public boolean checkSuppression(String codeFingerprint) {
        long fpCount = feedbackRepository.countFalsePositivesByFingerprint(codeFingerprint);
        return fpCount >= 3;
    }

    public String generateFingerprint(Finding finding) {
        String content = Optional.ofNullable(finding.getCodeSnippet()).orElse("")
                + "|" + Optional.ofNullable(finding.getVulnerabilityType()).orElse("")
                + "|" + Optional.ofNullable(finding.getFilePath()).orElse("");
        return sha256(content);
    }

    private String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }
}
