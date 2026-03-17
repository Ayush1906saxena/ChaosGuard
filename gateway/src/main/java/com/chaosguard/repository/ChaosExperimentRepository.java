package com.chaosguard.repository;

import com.chaosguard.model.ChaosExperiment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ChaosExperimentRepository extends JpaRepository<ChaosExperiment, UUID> {
    List<ChaosExperiment> findByScanIdOrderByCreatedAtDesc(UUID scanId);
}
