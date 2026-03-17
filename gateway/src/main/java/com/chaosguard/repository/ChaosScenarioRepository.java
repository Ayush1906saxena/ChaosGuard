package com.chaosguard.repository;

import com.chaosguard.model.ChaosScenario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ChaosScenarioRepository extends JpaRepository<ChaosScenario, UUID> {

    List<ChaosScenario> findByScanId(UUID scanId);

    List<ChaosScenario> findByScanIdAndScenarioType(UUID scanId, String scenarioType);

    List<ChaosScenario> findByScanIdAndSeverity(UUID scanId, String severity);
}
