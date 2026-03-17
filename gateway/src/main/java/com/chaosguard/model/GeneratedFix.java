package com.chaosguard.model;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "generated_fixes")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GeneratedFix {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "scan_id", nullable = false)
    private UUID scanId;

    @Column(name = "finding_id", nullable = false)
    private UUID findingId;

    @Column(name = "file_path", nullable = false)
    private String filePath;

    @Column(name = "original_code", columnDefinition = "TEXT")
    private String originalCode;

    @Column(name = "fixed_code", columnDefinition = "TEXT")
    private String fixedCode;

    @Column(name = "diff_patch", columnDefinition = "TEXT")
    private String diffPatch;

    @Column(name = "explanation", columnDefinition = "TEXT")
    private String explanation;

    @Column(name = "confidence_score")
    private Double confidenceScore;

    @Type(JsonType.class)
    @Column(name = "metadata", columnDefinition = "jsonb")
    private Map<String, Object> metadata;

    @Column(name = "is_applied")
    @Builder.Default
    private Boolean isApplied = false;

    @Column(name = "syntax_valid")
    private Boolean syntaxValid;

    @Column(name = "compile_valid")
    private Boolean compileValid;

    @Column(name = "tests_pass")
    private Boolean testsPass;

    @Column(name = "sandbox_output", columnDefinition = "TEXT")
    private String sandboxOutput;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", insertable = false, updatable = false)
    @com.fasterxml.jackson.annotation.JsonIgnore
    private Scan scan;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "finding_id", insertable = false, updatable = false)
    @com.fasterxml.jackson.annotation.JsonIgnore
    private Finding finding;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
