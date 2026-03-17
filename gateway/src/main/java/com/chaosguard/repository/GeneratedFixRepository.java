package com.chaosguard.repository;

import com.chaosguard.model.GeneratedFix;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface GeneratedFixRepository extends JpaRepository<GeneratedFix, UUID> {

    List<GeneratedFix> findByScanId(UUID scanId);

    List<GeneratedFix> findByFindingId(UUID findingId);

    List<GeneratedFix> findByScanIdAndIsApplied(UUID scanId, Boolean isApplied);
}
