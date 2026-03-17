package com.chaosguard.repository;

import com.chaosguard.model.AttackChain;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface AttackChainRepository extends JpaRepository<AttackChain, UUID> {

    List<AttackChain> findByScanId(UUID scanId);

    List<AttackChain> findByScanIdAndSeverity(UUID scanId, String severity);

    List<AttackChain> findByScanIdOrderBySeverityAsc(UUID scanId);
}
