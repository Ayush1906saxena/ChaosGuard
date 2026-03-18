"""Enhanced resilience scoring with per-service breakdown and trend analysis.

This module extracts and extends the scoring logic from the experiment runner,
providing granular per-service resilience metrics, recovery curve analysis,
blast radius measurement, and actionable recommendations.

Classes:
    ServiceScore: Resilience score for a single service.
    RecoveryCurve: Recovery shape analysis after chaos rollback.
    BlastRadiusMeasurement: Actual blast radius during an experiment.
    ResilienceReport: Complete resilience report for an experiment.
    ResilienceScorer: Computes resilience scores from experiment health data.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging
import math
import time

logger = logging.getLogger(__name__)


@dataclass
class ServiceScore:
    """Resilience score for a single service.

    Attributes:
        service_name: Name of the service being scored.
        availability_score: Percentage of successful health checks during chaos (0-100).
        recovery_time_ms: Milliseconds until the service recovered after rollback.
        degradation_score: How gracefully the service degraded under fault (0-100).
        cascade_impact: Fraction of downstream services affected by this service's
            failure (0-1).
        overall_score: Weighted composite of all sub-scores.
    """

    service_name: str
    availability_score: float = 0.0      # 0-100
    recovery_time_ms: float = 0.0        # Time to recover after rollback
    degradation_score: float = 0.0       # 0-100, how gracefully it degraded
    cascade_impact: float = 0.0          # 0-1, how much it affected downstream
    overall_score: float = 0.0           # Weighted composite

    def compute_overall(self, weights: Optional[dict] = None) -> float:
        """Compute the weighted overall resilience score for this service.

        Args:
            weights: Optional dict with keys ``availability``, ``recovery``,
                ``degradation``, and ``cascade``. Values should sum to 1.0.
                Falls back to sensible defaults if not provided.

        Returns:
            The computed overall score (0-100).
        """
        w = weights or {
            "availability": 0.35,
            "recovery": 0.25,
            "degradation": 0.25,
            "cascade": 0.15,
        }
        # Recovery score: inverse of recovery time (faster = better).
        # 30 000 ms (30 s) maps to a score of 0; 0 ms maps to 100.
        recovery_score = max(0, 100 - (self.recovery_time_ms / 300))  # 30s = 0 score

        self.overall_score = (
            w["availability"] * self.availability_score
            + w["recovery"] * recovery_score
            + w["degradation"] * self.degradation_score
            + w["cascade"] * (100 - self.cascade_impact * 100)
        )
        return self.overall_score

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON encoding."""
        return {
            "service": self.service_name,
            "availability": round(self.availability_score, 1),
            "recovery_time_ms": round(self.recovery_time_ms, 1),
            "degradation": round(self.degradation_score, 1),
            "cascade_impact": round(self.cascade_impact, 2),
            "overall": round(self.overall_score, 1),
        }


@dataclass
class RecoveryCurve:
    """Analyzes the shape of recovery after chaos rollback.

    Feed chronological ``(timestamp, health_value)`` pairs into ``timestamps``
    and ``health_values`` to classify the recovery pattern and compute
    time-to-recovery metrics.

    Attributes:
        timestamps: Monotonically increasing UNIX timestamps.
        health_values: Corresponding normalized health values in [0, 1].
    """

    timestamps: list[float] = field(default_factory=list)
    health_values: list[float] = field(default_factory=list)  # 0-1 normalized

    @property
    def recovery_type(self) -> str:
        """Classify the recovery curve shape.

        Returns one of:
            - ``"insufficient_data"`` -- fewer than 3 data points.
            - ``"immediate"`` -- first health value already above 0.9.
            - ``"exponential"`` -- fast initial gain then tapering off.
            - ``"logarithmic"`` -- slow start followed by rapid gain (concerning).
            - ``"linear"`` -- roughly even gain throughout.
        """
        if len(self.health_values) < 3:
            return "insufficient_data"

        # Check if recovery is immediate (first value > 0.9)
        if self.health_values[0] > 0.9:
            return "immediate"

        # Compare gain in first half vs second half
        midpoint = len(self.health_values) // 2
        first_half_gain = self.health_values[midpoint] - self.health_values[0]
        second_half_gain = self.health_values[-1] - self.health_values[midpoint]

        if first_half_gain > second_half_gain * 1.5:
            return "exponential"  # Fast initial recovery
        elif second_half_gain > first_half_gain * 1.5:
            return "logarithmic"  # Slow start, fast finish (concerning)
        else:
            return "linear"

    @property
    def time_to_90_pct(self) -> Optional[float]:
        """Seconds from the first data point until health reaches 90%.

        Returns:
            Elapsed seconds, or ``None`` if 90% was never reached.
        """
        if not self.timestamps or not self.health_values:
            return None
        for i, v in enumerate(self.health_values):
            if v >= 0.9:
                return self.timestamps[i] - self.timestamps[0]
        return None  # Never reached 90%

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON encoding."""
        return {
            "recovery_type": self.recovery_type,
            "time_to_90_pct_s": self.time_to_90_pct,
            "data_points": len(self.health_values),
        }


@dataclass
class BlastRadiusMeasurement:
    """Measures actual blast radius during a chaos experiment.

    By comparing the ``target_services`` (services explicitly injected with
    faults) to the full set of ``affected_services`` and
    ``unaffected_services``, this class quantifies how far a failure cascaded
    beyond the intended targets.

    Attributes:
        target_services: Services that were intentionally faulted.
        affected_services: All services that showed degradation (including targets).
        unaffected_services: Services that remained healthy throughout.
    """

    target_services: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    unaffected_services: list[str] = field(default_factory=list)

    @property
    def cascade_depth(self) -> int:
        """Count of non-target services that were affected by the experiment."""
        targets = set(self.target_services)
        return len([s for s in self.affected_services if s not in targets])

    @property
    def cascade_ratio(self) -> float:
        """Ratio of affected non-target services to total non-target services.

        Returns:
            A float in [0, 1]. Returns 0.0 when there are no non-target services.
        """
        targets = set(self.target_services)
        non_target_total = (
            len(self.affected_services) + len(self.unaffected_services) - len(targets)
        )
        if non_target_total <= 0:
            return 0.0
        cascaded = len([s for s in self.affected_services if s not in targets])
        return cascaded / non_target_total

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON encoding."""
        return {
            "target_services": self.target_services,
            "affected_services": self.affected_services,
            "unaffected_services": self.unaffected_services,
            "cascade_depth": self.cascade_depth,
            "cascade_ratio": round(self.cascade_ratio, 2),
        }


@dataclass
class ResilienceReport:
    """Complete resilience report for a chaos experiment.

    Call :meth:`compute` after populating ``service_scores`` (and optionally
    ``recovery_curve`` / ``blast_radius``) to derive the ``overall_score``,
    identify the ``weakest_service``, and generate ``recommendations``.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        overall_score: Composite score (0-100) with weakest-link penalty.
        service_scores: Per-service resilience breakdowns.
        recovery_curve: Optional aggregate recovery curve analysis.
        blast_radius: Optional blast radius measurement.
        hypothesis_summary: Optional dict summarizing the experiment hypothesis
            and whether it was confirmed.
        weakest_service: Name of the service with the lowest overall score.
        recommendations: Auto-generated actionable improvement suggestions.
        timestamp: UNIX timestamp when the report was created.
    """

    experiment_id: str
    overall_score: float = 0.0
    service_scores: list[ServiceScore] = field(default_factory=list)
    recovery_curve: Optional[RecoveryCurve] = None
    blast_radius: Optional[BlastRadiusMeasurement] = None
    hypothesis_summary: Optional[dict] = None
    weakest_service: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def compute(self) -> None:
        """Derive overall score, weakest service, and recommendations.

        Each :class:`ServiceScore` has its own ``compute_overall`` called first.
        The aggregate ``overall_score`` is the average of all service scores,
        capped so it never exceeds the weakest service's score by more than 20
        points (weakest-link penalty).
        """
        if not self.service_scores:
            return

        for svc in self.service_scores:
            svc.compute_overall()

        # Overall is the weighted average, but penalize if any service is very weak
        scores = [s.overall_score for s in self.service_scores]
        avg = sum(scores) / len(scores)
        min_score = min(scores)

        # Weakest link penalty: overall can't be more than 20 points above the worst
        self.overall_score = min(avg, min_score + 20)

        # Identify weakest service
        weakest = min(self.service_scores, key=lambda s: s.overall_score)
        self.weakest_service = weakest.service_name

        # Generate recommendations
        self._generate_recommendations()

    def _generate_recommendations(self) -> None:
        """Populate ``self.recommendations`` based on service scores and curves."""
        self.recommendations = []

        for svc in self.service_scores:
            if svc.availability_score < 50:
                self.recommendations.append(
                    f"CRITICAL: {svc.service_name} availability dropped below 50%. "
                    "Implement circuit breakers and health-based routing."
                )
            if svc.recovery_time_ms > 15000:
                self.recommendations.append(
                    f"WARNING: {svc.service_name} took "
                    f"{svc.recovery_time_ms / 1000:.1f}s to recover. "
                    "Add readiness probes and graceful shutdown handlers."
                )
            if svc.cascade_impact > 0.5:
                self.recommendations.append(
                    f"WARNING: {svc.service_name} failure cascaded to >50% of "
                    "downstream services. Implement bulkhead isolation and async "
                    "communication patterns."
                )

        if (
            self.recovery_curve
            and self.recovery_curve.recovery_type == "logarithmic"
        ):
            self.recommendations.append(
                "Recovery pattern is logarithmic (slow start). Consider "
                "implementing connection pool warm-up and cache pre-loading "
                "after restarts."
            )

        if self.blast_radius and self.blast_radius.cascade_ratio > 0.3:
            self.recommendations.append(
                f"Blast radius exceeded expectations: "
                f"{self.blast_radius.cascade_depth} non-target services affected. "
                "Review service dependencies and add fallbacks."
            )

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON encoding."""
        return {
            "experiment_id": self.experiment_id,
            "overall_score": round(self.overall_score, 1),
            "weakest_service": self.weakest_service,
            "service_scores": [s.to_dict() for s in self.service_scores],
            "recovery_curve": (
                self.recovery_curve.to_dict() if self.recovery_curve else None
            ),
            "blast_radius": (
                self.blast_radius.to_dict() if self.blast_radius else None
            ),
            "hypothesis_summary": self.hypothesis_summary,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


class ResilienceScorer:
    """Computes resilience scores from experiment health data.

    Usage::

        scorer = ResilienceScorer(experiment_id="abc-123")

        # During baseline phase
        scorer.record_health("baseline", "api", {"healthy": True, "response_time": 42})

        # During chaos phase
        scorer.record_health("chaos", "api", {"healthy": False, "response_time": 0})

        # During recovery phase
        scorer.record_health("recovery", "api", {"healthy": True, "response_time": 55})

        report = scorer.compute_report(target_services=["api"])
        print(report.to_dict())

    Attributes:
        experiment_id: Identifier for the experiment being scored.
        baseline_health: Per-service health snapshots collected before fault injection.
        chaos_health: Per-service health snapshots collected during fault injection.
        recovery_health: Per-service health snapshots collected after rollback.
    """

    def __init__(self, experiment_id: str) -> None:
        self.experiment_id = experiment_id
        self.baseline_health: dict[str, list[dict]] = {}  # service -> health snapshots
        self.chaos_health: dict[str, list[dict]] = {}
        self.recovery_health: dict[str, list[dict]] = {}

    def record_health(self, phase: str, service: str, health: dict) -> None:
        """Record a health data point for a service during a phase.

        Args:
            phase: One of ``"baseline"``, ``"chaos"``, or ``"recovery"``.
            service: Name of the service (e.g. ``"api"``).
            health: Dict with at least ``"healthy"`` (bool). May also contain
                ``"response_time"`` (numeric, milliseconds) and other metadata.
        """
        store = {
            "baseline": self.baseline_health,
            "chaos": self.chaos_health,
            "recovery": self.recovery_health,
        }.get(phase)

        if store is None:
            logger.warning(
                "[scoring] Unknown phase '%s'; ignoring health record", phase
            )
            return

        if service not in store:
            store[service] = []
        store[service].append({**health, "timestamp": time.time()})

    def compute_report(self, target_services: list[str]) -> ResilienceReport:
        """Generate a complete resilience report from recorded health data.

        Args:
            target_services: Names of services that were intentionally faulted.

        Returns:
            A fully computed :class:`ResilienceReport` with per-service scores,
            recovery curve, blast radius, and recommendations.
        """
        report = ResilienceReport(experiment_id=self.experiment_id)
        all_services = set(
            list(self.baseline_health.keys())
            + list(self.chaos_health.keys())
            + list(self.recovery_health.keys())
        )

        affected: list[str] = []
        unaffected: list[str] = []

        for service in all_services:
            score = self._score_service(service)
            report.service_scores.append(score)

            if score.availability_score < 95:
                affected.append(service)
            else:
                unaffected.append(service)

        # Build recovery curve from aggregate data
        report.recovery_curve = self._build_recovery_curve()

        # Blast radius
        report.blast_radius = BlastRadiusMeasurement(
            target_services=target_services,
            affected_services=affected,
            unaffected_services=unaffected,
        )

        report.compute()
        return report

    def _score_service(self, service: str) -> ServiceScore:
        """Compute resilience score for a single service.

        Evaluates availability during chaos, recovery time after rollback, and
        graceful degradation by comparing baseline vs chaos response times.

        Args:
            service: Name of the service to score.

        Returns:
            A :class:`ServiceScore` with sub-scores populated (but
            ``compute_overall`` not yet called -- that happens in
            :meth:`ResilienceReport.compute`).
        """
        score = ServiceScore(service_name=service)

        # Availability: percentage of successful health checks during chaos
        chaos_checks = self.chaos_health.get(service, [])
        if chaos_checks:
            successful = sum(1 for h in chaos_checks if h.get("healthy", False))
            score.availability_score = (successful / len(chaos_checks)) * 100
        else:
            score.availability_score = 100  # No data = assume healthy

        # Recovery time: milliseconds from first recovery probe to first healthy probe
        recovery_checks = self.recovery_health.get(service, [])
        if recovery_checks:
            first_ts = recovery_checks[0].get("timestamp", 0)
            for check in recovery_checks:
                if check.get("healthy", False):
                    score.recovery_time_ms = (check["timestamp"] - first_ts) * 1000
                    break
            else:
                score.recovery_time_ms = 30000  # Never recovered within window

        # Degradation: compare baseline response times to chaos response times
        baseline_times = [
            h.get("response_time", 0)
            for h in self.baseline_health.get(service, [])
            if h.get("response_time")
        ]
        chaos_times = [
            h.get("response_time", 0)
            for h in chaos_checks
            if h.get("response_time")
        ]

        if baseline_times and chaos_times:
            baseline_avg = sum(baseline_times) / len(baseline_times)
            chaos_avg = sum(chaos_times) / len(chaos_times)
            if baseline_avg > 0:
                degradation_factor = chaos_avg / baseline_avg
                # A factor of 1.0 (no change) yields 100; factor of 3.0 yields 0
                score.degradation_score = max(0, 100 - (degradation_factor - 1) * 50)
            else:
                score.degradation_score = 100
        else:
            score.degradation_score = 50  # Unknown

        return score

    def _build_recovery_curve(self) -> RecoveryCurve:
        """Build an aggregate recovery curve across all services.

        Merges recovery health checks from every service into a single
        time-ordered sequence of ``(timestamp, health_value)`` pairs where
        health is 1.0 for healthy and 0.0 otherwise.

        Returns:
            A :class:`RecoveryCurve` instance (may contain zero data points
            if no recovery data was recorded).
        """
        curve = RecoveryCurve()

        all_recovery: list[dict] = []
        for service, checks in self.recovery_health.items():
            for check in checks:
                all_recovery.append(check)

        if not all_recovery:
            return curve

        all_recovery.sort(key=lambda h: h.get("timestamp", 0))

        for check in all_recovery:
            curve.timestamps.append(check.get("timestamp", 0))
            curve.health_values.append(1.0 if check.get("healthy", False) else 0.0)

        return curve
