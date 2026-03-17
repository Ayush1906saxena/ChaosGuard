package com.chaosguard.repository;

import com.chaosguard.model.Scan;
import com.chaosguard.model.Scan.ScanStatus;
import com.chaosguard.model.Scan.ScanTier;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface ScanRepository extends JpaRepository<Scan, UUID> {

    List<Scan> findByStatus(ScanStatus status);

    List<Scan> findByTier(ScanTier tier);

    List<Scan> findByRepoUrl(String repoUrl);

    Page<Scan> findByStatusIn(List<ScanStatus> statuses, Pageable pageable);

    @Query("SELECT s FROM Scan s WHERE s.status NOT IN ('COMPLETE', 'FAILED') ORDER BY s.createdAt DESC")
    List<Scan> findActiveScans();

    @Query("SELECT COUNT(s) FROM Scan s WHERE s.status NOT IN ('COMPLETE', 'FAILED')")
    long countActiveScans();

    @Query("SELECT s FROM Scan s WHERE s.repoUrl = :repoUrl AND s.branch = :branch ORDER BY s.createdAt DESC")
    List<Scan> findByRepoUrlAndBranch(@Param("repoUrl") String repoUrl, @Param("branch") String branch);

    @Query("SELECT s FROM Scan s WHERE s.createdAt >= :since ORDER BY s.createdAt DESC")
    Page<Scan> findRecentScans(@Param("since") Instant since, Pageable pageable);

    @Query("SELECT s FROM Scan s WHERE s.status = 'FAILED' AND s.createdAt >= :since")
    List<Scan> findFailedScansSince(@Param("since") Instant since);

    @Query("SELECT s.tier, s.status, COUNT(s) FROM Scan s WHERE s.status IN ('QUEUED', 'CLONING', 'INDEXING', 'ANALYZING', 'GENERATING_FIXES') GROUP BY s.tier, s.status")
    List<Object[]> countByStatusAndTier();
}
