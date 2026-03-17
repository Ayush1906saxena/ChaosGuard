package com.chaosguard.repository;

import com.chaosguard.model.Finding;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface FindingRepository extends JpaRepository<Finding, UUID> {

    List<Finding> findByScanId(UUID scanId);

    Page<Finding> findByScanId(UUID scanId, Pageable pageable);

    List<Finding> findByScanIdAndSeverity(UUID scanId, String severity);

    List<Finding> findByScanIdAndVulnerabilityType(UUID scanId, String vulnerabilityType);

    @Query("SELECT f FROM Finding f WHERE f.scanId = :scanId AND f.severity = :severity AND f.isFalsePositive = false")
    List<Finding> findConfirmedByScanIdAndSeverity(@Param("scanId") UUID scanId, @Param("severity") String severity);

    @Query("SELECT f FROM Finding f WHERE f.scanId = :scanId AND f.isFalsePositive = false ORDER BY f.cvssScore DESC NULLS LAST")
    List<Finding> findByScanIdOrderBySeverity(@Param("scanId") UUID scanId);

    @Query("SELECT f FROM Finding f WHERE f.scanId = :scanId AND f.filePath LIKE %:filePath%")
    List<Finding> findByScanIdAndFilePathContaining(@Param("scanId") UUID scanId, @Param("filePath") String filePath);

    @Query("SELECT f FROM Finding f WHERE f.scanId = :scanId AND " +
           "(:severity IS NULL OR f.severity = :severity) AND " +
           "(:vulnerabilityType IS NULL OR f.vulnerabilityType = :vulnerabilityType) AND " +
           "(:isFalsePositive IS NULL OR f.isFalsePositive = :isFalsePositive)")
    Page<Finding> findWithFilters(@Param("scanId") UUID scanId,
                                  @Param("severity") String severity,
                                  @Param("vulnerabilityType") String vulnerabilityType,
                                  @Param("isFalsePositive") Boolean isFalsePositive,
                                  Pageable pageable);

    @Query("SELECT DISTINCT f.vulnerabilityType FROM Finding f WHERE f.scanId = :scanId")
    List<String> findDistinctVulnerabilityTypesByScanId(@Param("scanId") UUID scanId);

    @Query("SELECT f.severity, COUNT(f) FROM Finding f WHERE f.scanId = :scanId GROUP BY f.severity")
    List<Object[]> countBySeverityForScan(@Param("scanId") UUID scanId);
}
