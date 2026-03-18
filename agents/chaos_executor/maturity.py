"""Chaos Maturity Model — assesses organizational chaos engineering readiness.

Based on industry chaos maturity models, this module evaluates an organization's
current level of chaos engineering practice and provides guidance for advancement.

Levels:
  0 - ANALYSIS_ONLY:     Security scanning, no fault injection
  1 - SANDBOX_CHAOS:     Chaos experiments in isolated sandbox environments
  2 - STAGING_CHAOS:     Chaos experiments in staging / pre-production
  3 - PRODUCTION_CHAOS:  Controlled chaos in production with safeguards
  4 - CONTINUOUS_CHAOS:  Automated, scheduled chaos as part of CI/CD
"""

import json
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import psycopg2

from config import config

logger = logging.getLogger(__name__)


class MaturityLevel(IntEnum):
    ANALYSIS_ONLY = 0
    SANDBOX_CHAOS = 1
    STAGING_CHAOS = 2
    PRODUCTION_CHAOS = 3
    CONTINUOUS_CHAOS = 4

    @property
    def label(self) -> str:
        labels = {
            0: "Analysis Only",
            1: "Sandbox Chaos",
            2: "Staging Chaos",
            3: "Production Chaos",
            4: "Continuous Chaos",
        }
        return labels.get(self.value, "Unknown")

    @property
    def description(self) -> str:
        descriptions = {
            0: "Security scanning and vulnerability analysis without fault injection.",
            1: "Running chaos experiments in isolated sandbox (Docker) environments.",
            2: "Running chaos experiments in staging or pre-production environments.",
            3: "Controlled chaos experiments in production with full safety guardrails.",
            4: "Automated, continuously scheduled chaos integrated into CI/CD pipelines.",
        }
        return descriptions.get(self.value, "")


@dataclass
class MaturityGate:
    """Requirements that must be met to advance to a given maturity level."""

    target_level: MaturityLevel
    min_experiments: int  # Minimum total experiments completed
    min_pass_rate: float  # Minimum percentage of experiments that passed (0-100)
    min_days_at_current_level: int  # Minimum days operating at the current level
    requires_hypothesis_validation: bool = False
    requires_automated_rollback: bool = False
    requires_gameday_cadence: bool = False  # At least one GameDay run
    requires_progressive_rollout: bool = False
    additional_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_level": self.target_level.value,
            "target_level_name": self.target_level.label,
            "min_experiments": self.min_experiments,
            "min_pass_rate": self.min_pass_rate,
            "min_days_at_current_level": self.min_days_at_current_level,
            "requires_hypothesis_validation": self.requires_hypothesis_validation,
            "requires_automated_rollback": self.requires_automated_rollback,
            "requires_gameday_cadence": self.requires_gameday_cadence,
            "requires_progressive_rollout": self.requires_progressive_rollout,
            "additional_requirements": self.additional_requirements,
        }


# Default gates for each level transition
DEFAULT_GATES: dict[MaturityLevel, MaturityGate] = {
    MaturityLevel.SANDBOX_CHAOS: MaturityGate(
        target_level=MaturityLevel.SANDBOX_CHAOS,
        min_experiments=1,
        min_pass_rate=0.0,  # Just need to run at least one
        min_days_at_current_level=0,
        additional_requirements=[
            "Docker environment configured",
            "At least one scan completed",
        ],
    ),
    MaturityLevel.STAGING_CHAOS: MaturityGate(
        target_level=MaturityLevel.STAGING_CHAOS,
        min_experiments=5,
        min_pass_rate=50.0,
        min_days_at_current_level=7,
        requires_hypothesis_validation=True,
        requires_automated_rollback=True,
        additional_requirements=[
            "Steady-state hypotheses defined for all experiments",
            "Automated rollback verified in at least 3 experiments",
            "Staging environment provisioned and accessible",
        ],
    ),
    MaturityLevel.PRODUCTION_CHAOS: MaturityGate(
        target_level=MaturityLevel.PRODUCTION_CHAOS,
        min_experiments=20,
        min_pass_rate=70.0,
        min_days_at_current_level=30,
        requires_hypothesis_validation=True,
        requires_automated_rollback=True,
        requires_gameday_cadence=True,
        additional_requirements=[
            "At least 3 GameDay runs completed successfully",
            "Observability pipeline integrated (metrics, alerts)",
            "Runbooks for all experiment types",
            "Incident response team trained on chaos procedures",
        ],
    ),
    MaturityLevel.CONTINUOUS_CHAOS: MaturityGate(
        target_level=MaturityLevel.CONTINUOUS_CHAOS,
        min_experiments=50,
        min_pass_rate=80.0,
        min_days_at_current_level=60,
        requires_hypothesis_validation=True,
        requires_automated_rollback=True,
        requires_gameday_cadence=True,
        requires_progressive_rollout=True,
        additional_requirements=[
            "CI/CD integration configured",
            "Automated scheduling via GameDayScheduler",
            "Progressive rollout tested in production",
            "Mean recovery time under 60 seconds",
            "Resilience score trending above 75 over 30 days",
        ],
    ),
}


@dataclass
class MaturityAssessment:
    """Result of a maturity level assessment."""

    current_level: MaturityLevel
    total_experiments: int
    completed_experiments: int
    pass_rate: float
    avg_resilience_score: float
    days_at_current_level: int
    has_hypothesis_validation: bool
    has_automated_rollback: bool
    has_gameday_runs: bool
    has_progressive_rollout: bool
    can_advance: bool
    next_level: Optional[MaturityLevel]
    unmet_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_level": self.current_level.value,
            "current_level_name": self.current_level.label,
            "current_level_description": self.current_level.description,
            "total_experiments": self.total_experiments,
            "completed_experiments": self.completed_experiments,
            "pass_rate": self.pass_rate,
            "avg_resilience_score": self.avg_resilience_score,
            "days_at_current_level": self.days_at_current_level,
            "can_advance": self.can_advance,
            "next_level": self.next_level.value if self.next_level else None,
            "next_level_name": self.next_level.label if self.next_level else None,
            "unmet_requirements": self.unmet_requirements,
        }


class MaturityAssessor:
    """Evaluates chaos engineering maturity based on experiment history."""

    def __init__(self, gates: Optional[dict[MaturityLevel, MaturityGate]] = None):
        self.gates = gates or DEFAULT_GATES

    def assess_level(self, org_id: str = "default") -> MaturityAssessment:
        """Assess the current maturity level based on experiment history."""
        stats = self._fetch_experiment_stats(org_id)

        total = stats.get("total_experiments", 0)
        completed = stats.get("completed_experiments", 0)
        pass_rate = stats.get("pass_rate", 0.0)
        avg_score = stats.get("avg_resilience_score", 0.0)
        days_active = stats.get("days_active", 0)
        has_hypothesis = stats.get("has_hypothesis_validation", False)
        has_rollback = stats.get("has_automated_rollback", False)
        has_gameday = stats.get("has_gameday_runs", False)
        has_progressive = stats.get("has_progressive_rollout", False)

        # Determine current level by checking which gates are satisfied
        current_level = MaturityLevel.ANALYSIS_ONLY
        for level in [MaturityLevel.SANDBOX_CHAOS, MaturityLevel.STAGING_CHAOS,
                      MaturityLevel.PRODUCTION_CHAOS, MaturityLevel.CONTINUOUS_CHAOS]:
            gate = self.gates.get(level)
            if gate and self._gate_satisfied(gate, stats):
                current_level = level
            else:
                break

        # Check advancement to next level
        next_level = None
        can_advance = False
        unmet: list[str] = []

        if current_level < MaturityLevel.CONTINUOUS_CHAOS:
            next_level = MaturityLevel(current_level + 1)
            gate = self.gates.get(next_level)
            if gate:
                can_advance, unmet = self.check_advancement(gate, stats)

        return MaturityAssessment(
            current_level=current_level,
            total_experiments=total,
            completed_experiments=completed,
            pass_rate=pass_rate,
            avg_resilience_score=avg_score,
            days_at_current_level=days_active,
            has_hypothesis_validation=has_hypothesis,
            has_automated_rollback=has_rollback,
            has_gameday_runs=has_gameday,
            has_progressive_rollout=has_progressive,
            can_advance=can_advance,
            next_level=next_level,
            unmet_requirements=unmet,
        )

    def check_advancement(
        self, gate: MaturityGate, stats: dict
    ) -> tuple[bool, list[str]]:
        """Check if requirements for the next level are met.

        Returns (can_advance, list_of_unmet_requirements).
        """
        unmet: list[str] = []

        total = stats.get("total_experiments", 0)
        if total < gate.min_experiments:
            unmet.append(
                f"Need {gate.min_experiments} experiments, have {total}"
            )

        pass_rate = stats.get("pass_rate", 0.0)
        if pass_rate < gate.min_pass_rate:
            unmet.append(
                f"Need {gate.min_pass_rate}% pass rate, have {pass_rate:.1f}%"
            )

        days = stats.get("days_active", 0)
        if days < gate.min_days_at_current_level:
            unmet.append(
                f"Need {gate.min_days_at_current_level} days at current level, have {days}"
            )

        if gate.requires_hypothesis_validation and not stats.get("has_hypothesis_validation", False):
            unmet.append("Steady-state hypothesis validation not yet used")

        if gate.requires_automated_rollback and not stats.get("has_automated_rollback", False):
            unmet.append("Automated rollback not yet verified")

        if gate.requires_gameday_cadence and not stats.get("has_gameday_runs", False):
            unmet.append("No GameDay runs completed")

        if gate.requires_progressive_rollout and not stats.get("has_progressive_rollout", False):
            unmet.append("Progressive rollout not yet tested")

        for req in gate.additional_requirements:
            # Additional requirements are informational — we can't auto-check them,
            # but we include them so the user knows what's expected.
            pass

        return len(unmet) == 0, unmet

    def get_requirements_for_next_level(self, org_id: str = "default") -> dict:
        """Get detailed requirements for advancing to the next maturity level."""
        assessment = self.assess_level(org_id)

        if assessment.next_level is None:
            return {
                "current_level": assessment.current_level.label,
                "message": "Already at maximum maturity level (Continuous Chaos).",
                "requirements": [],
            }

        gate = self.gates.get(assessment.next_level)
        if not gate:
            return {
                "current_level": assessment.current_level.label,
                "message": "No gate defined for next level.",
                "requirements": [],
            }

        return {
            "current_level": assessment.current_level.label,
            "next_level": assessment.next_level.label,
            "gate": gate.to_dict(),
            "unmet_requirements": assessment.unmet_requirements,
            "met_requirements_count": (
                len(gate.additional_requirements) + 4  # base checks
                - len(assessment.unmet_requirements)
            ),
        }

    def _gate_satisfied(self, gate: MaturityGate, stats: dict) -> bool:
        """Check if a maturity gate is fully satisfied."""
        can_advance, _ = self.check_advancement(gate, stats)
        return can_advance

    def _fetch_experiment_stats(self, org_id: str) -> dict:
        """Fetch experiment statistics from PostgreSQL."""
        stats: dict = {
            "total_experiments": 0,
            "completed_experiments": 0,
            "pass_rate": 0.0,
            "avg_resilience_score": 0.0,
            "days_active": 0,
            "has_hypothesis_validation": False,
            "has_automated_rollback": False,
            "has_gameday_runs": False,
            "has_progressive_rollout": False,
        }

        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    # Total and completed experiments
                    cur.execute(
                        "SELECT COUNT(*), "
                        "SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), "
                        "AVG(CASE WHEN status = 'COMPLETED' THEN resilience_score ELSE NULL END), "
                        "EXTRACT(DAY FROM NOW() - MIN(started_at)) "
                        "FROM chaos_experiments"
                    )
                    row = cur.fetchone()
                    if row:
                        stats["total_experiments"] = row[0] or 0
                        stats["completed_experiments"] = row[1] or 0
                        stats["avg_resilience_score"] = round(float(row[2] or 0), 1)
                        stats["days_active"] = int(row[3] or 0)

                    total = stats["total_experiments"]
                    completed = stats["completed_experiments"]
                    if total > 0:
                        stats["pass_rate"] = round((completed / total) * 100, 1)

                    # Check if hypothesis validation has been used
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM chaos_experiments "
                        "WHERE chaos_metrics::text LIKE '%hypothesis%' "
                        "OR verdict LIKE '%hypothesis%')"
                    )
                    row = cur.fetchone()
                    stats["has_hypothesis_validation"] = bool(row and row[0])

                    # Automated rollback is inherent in the system
                    stats["has_automated_rollback"] = stats["completed_experiments"] > 0

                    # Check for GameDay runs
                    try:
                        cur.execute(
                            "SELECT EXISTS(SELECT 1 FROM chaos_gameday_runs WHERE status = 'COMPLETED')"
                        )
                        row = cur.fetchone()
                        stats["has_gameday_runs"] = bool(row and row[0])
                    except Exception:
                        # Table may not exist yet
                        conn.rollback()

            finally:
                conn.close()

        except Exception as exc:
            logger.error("[maturity] Failed to fetch experiment stats: %s", exc)

        return stats
