package com.chaosguard.repository;

import com.chaosguard.model.FindingFeedback;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface FindingFeedbackRepository extends JpaRepository<FindingFeedback, UUID> {

    List<FindingFeedback> findByFindingId(UUID findingId);

    List<FindingFeedback> findByCodeFingerprint(String codeFingerprint);

    @Query("SELECT ff FROM FindingFeedback ff WHERE ff.label = 'FALSE_POSITIVE' AND ff.codeFingerprint = :fingerprint")
    List<FindingFeedback> findFalsePositivesByFingerprint(@Param("fingerprint") String fingerprint);

    @Query("SELECT COUNT(ff) FROM FindingFeedback ff WHERE ff.label = 'FALSE_POSITIVE' AND ff.codeFingerprint = :fingerprint")
    long countFalsePositivesByFingerprint(@Param("fingerprint") String fingerprint);
}
