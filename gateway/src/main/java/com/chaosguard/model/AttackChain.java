package com.chaosguard.model;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import com.fasterxml.jackson.annotation.JsonIgnore;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "attack_chains")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AttackChain {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "scan_id", nullable = false)
    private UUID scanId;

    @Column(name = "title", nullable = false)
    private String title;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "severity", nullable = false)
    private String severity;

    @Column(name = "impact", columnDefinition = "TEXT")
    private String impact;

    @Column(name = "likelihood")
    private String likelihood;

    @Type(JsonType.class)
    @Column(name = "chain_steps", columnDefinition = "jsonb")
    private List<Map<String, Object>> chainSteps;

    @Type(JsonType.class)
    @Column(name = "finding_ids", columnDefinition = "jsonb")
    private List<UUID> findingIds;

    @Type(JsonType.class)
    @Column(name = "mitigations", columnDefinition = "jsonb")
    private List<String> mitigations;

    @Column(name = "exploit_complexity")
    private String exploitComplexity;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", insertable = false, updatable = false)
    private Scan scan;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
