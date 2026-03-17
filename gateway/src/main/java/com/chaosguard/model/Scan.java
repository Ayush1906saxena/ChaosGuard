package com.chaosguard.model;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "scans")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Scan {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "repo_url", nullable = false)
    private String repoUrl;

    @Column(name = "branch")
    private String branch;

    @Enumerated(EnumType.STRING)
    @Column(name = "tier", nullable = false)
    private ScanTier tier;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private ScanStatus status;

    @Type(JsonType.class)
    @Column(name = "repo_metadata", columnDefinition = "jsonb")
    private Map<String, Object> repoMetadata;

    @Type(JsonType.class)
    @Column(name = "summary", columnDefinition = "jsonb")
    private Map<String, Object> summary;

    @Column(name = "error_message")
    private String errorMessage;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
        if (status == null) {
            status = ScanStatus.QUEUED;
        }
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    public enum ScanTier {
        RECON,
        HUNTER,
        SIEGE,
        LIVE
    }

    public enum ScanStatus {
        QUEUED,
        CLONING,
        CLONING_COMPLETE,
        INDEXING,
        INDEXING_COMPLETE,
        ANALYZING,
        GENERATING_FIXES,
        COMPLETE,
        FAILED
    }
}
