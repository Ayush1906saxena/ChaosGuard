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
@Table(name = "chaos_scenarios")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChaosScenario {

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

    @Column(name = "scenario_type", nullable = false)
    private String scenarioType;

    @Column(name = "target_component")
    private String targetComponent;

    @Type(JsonType.class)
    @Column(name = "injection_points", columnDefinition = "jsonb")
    private List<Map<String, Object>> injectionPoints;

    @Type(JsonType.class)
    @Column(name = "expected_impact", columnDefinition = "jsonb")
    private Map<String, Object> expectedImpact;

    @Type(JsonType.class)
    @Column(name = "blast_radius", columnDefinition = "jsonb")
    private Map<String, Object> blastRadius;

    @Column(name = "severity", nullable = false)
    private String severity;

    @Type(JsonType.class)
    @Column(name = "prerequisites", columnDefinition = "jsonb")
    private List<String> prerequisites;

    @Type(JsonType.class)
    @Column(name = "recovery_steps", columnDefinition = "jsonb")
    private List<String> recoverySteps;

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
