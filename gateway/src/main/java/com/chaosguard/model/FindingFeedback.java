package com.chaosguard.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "finding_feedback")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FindingFeedback {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "finding_id", nullable = false)
    private UUID findingId;

    @Enumerated(EnumType.STRING)
    @Column(name = "label", nullable = false)
    private FeedbackLabel label;

    @Column(name = "user_comment", columnDefinition = "TEXT")
    private String userComment;

    @Column(name = "code_fingerprint", nullable = false)
    private String codeFingerprint;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "finding_id", insertable = false, updatable = false)
    private Finding finding;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }

    public enum FeedbackLabel {
        TRUE_POSITIVE,
        FALSE_POSITIVE,
        WONT_FIX
    }
}
