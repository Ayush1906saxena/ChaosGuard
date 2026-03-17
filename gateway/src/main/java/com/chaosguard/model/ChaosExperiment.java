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
@Table(name = "chaos_experiments")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChaosExperiment {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "scan_id", nullable = false)
    private UUID scanId;

    @Column(name = "scenario_id")
    private String scenarioId;

    @Column(name = "status", nullable = false)
    @Builder.Default
    private String status = "PENDING";

    @Type(JsonType.class)
    @Column(name = "experiment_plan", columnDefinition = "jsonb")
    private Map<String, Object> experimentPlan;

    @Type(JsonType.class)
    @Column(name = "baseline_metrics", columnDefinition = "jsonb")
    private Map<String, Object> baselineMetrics;

    @Type(JsonType.class)
    @Column(name = "chaos_metrics", columnDefinition = "jsonb")
    private Map<String, Object> chaosMetrics;

    @Type(JsonType.class)
    @Column(name = "recovery_metrics", columnDefinition = "jsonb")
    private Map<String, Object> recoveryMetrics;

    @Column(name = "resilience_score")
    private Double resilienceScore;

    @Column(name = "recovery_time_s")
    private Double recoveryTimeS;

    @Type(JsonType.class)
    @Column(name = "faults_injected", columnDefinition = "jsonb")
    private List<Map<String, Object>> faultsInjected;

    @Type(JsonType.class)
    @Column(name = "health_timeline", columnDefinition = "jsonb")
    private List<Map<String, Object>> healthTimeline;

    @Column(name = "verdict", columnDefinition = "TEXT")
    private String verdict;

    @Type(JsonType.class)
    @Column(name = "recommendations", columnDefinition = "jsonb")
    private List<String> recommendations;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", insertable = false, updatable = false)
    @com.fasterxml.jackson.annotation.JsonIgnore
    private Scan scan;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
