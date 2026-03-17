package com.chaosguard.model;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "findings")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Finding {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "scan_id", nullable = false)
    private UUID scanId;

    @Column(name = "file_path", nullable = false)
    private String filePath;

    @Column(name = "line_start")
    private Integer lineStart;

    @Column(name = "line_end")
    private Integer lineEnd;

    @Column(name = "vulnerability_type", nullable = false)
    private String vulnerabilityType;

    @Column(name = "severity", nullable = false)
    private String severity;

    @Column(name = "confidence")
    private String confidence;

    @Column(name = "title", nullable = false)
    private String title;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "code_snippet", columnDefinition = "TEXT")
    private String codeSnippet;

    @Column(name = "remediation", columnDefinition = "TEXT")
    private String remediation;

    @Column(name = "cwe_id")
    private String cweId;

    @Column(name = "cvss_score")
    private Double cvssScore;

    @Column(name = "owasp_category")
    private String owaspCategory;

    @Type(JsonType.class)
    @Column(name = "references", columnDefinition = "jsonb")
    private List<String> references;

    @Type(JsonType.class)
    @Column(name = "metadata", columnDefinition = "jsonb")
    private Map<String, Object> metadata;

    @Column(name = "is_false_positive")
    @Builder.Default
    private Boolean isFalsePositive = false;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", insertable = false, updatable = false)
    private Scan scan;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
