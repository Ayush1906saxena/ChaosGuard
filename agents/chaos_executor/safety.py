"""Safety Controller — gates all chaos actions with blast-radius limits,
timeouts, approval workflows, and emergency stop via Redis."""

import asyncio
import logging
import time
from dataclasses import dataclass

import redis

from config import config

logger = logging.getLogger(__name__)


@dataclass
class SafetyLimits:
    max_blast_radius: int = 3            # max containers affected at once
    max_experiment_duration_s: int = 300  # 5-minute hard cap
    max_concurrent_experiments: int = 1
    approval_timeout_s: int = 600        # 10 minutes to approve
    auto_rollback_on_error: bool = True
    require_approval: bool = True


class SafetyController:
    """Central authority that gates all chaos execution."""

    def __init__(self, limits: SafetyLimits | None = None):
        self.limits = limits or SafetyLimits()
        self._redis = redis.Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
        )

    def validate_experiment(self, experiment_plan: dict) -> list[str]:
        """Return a list of validation errors. Empty = OK."""
        errors = []

        faults = experiment_plan.get("faults", [])
        if not faults:
            errors.append("No faults defined in experiment plan")

        # Check blast radius
        affected_services = set()
        for fault in faults:
            affected_services.add(fault.get("target_service", ""))
        if len(affected_services) > self.limits.max_blast_radius:
            errors.append(
                f"Blast radius {len(affected_services)} exceeds limit "
                f"of {self.limits.max_blast_radius} services"
            )

        # Check duration
        total_duration = experiment_plan.get("total_duration_s", 0)
        if total_duration > self.limits.max_experiment_duration_s:
            errors.append(
                f"Duration {total_duration}s exceeds limit of "
                f"{self.limits.max_experiment_duration_s}s"
            )

        return errors

    async def request_approval(self, experiment_id: str) -> bool:
        """Block until the experiment is approved or rejected via Redis."""
        if not self.limits.require_approval:
            return True

        approval_key = f"chaos:approval:{experiment_id}"
        logger.info("[safety] Waiting for approval on %s (timeout=%ds)",
                     experiment_id, self.limits.approval_timeout_s)

        deadline = time.time() + self.limits.approval_timeout_s
        while time.time() < deadline:
            val = self._redis.get(approval_key)
            if val == "approved":
                logger.info("[safety] Experiment %s APPROVED", experiment_id)
                return True
            if val == "rejected":
                logger.info("[safety] Experiment %s REJECTED", experiment_id)
                return False
            await asyncio.sleep(1)

        logger.warning("[safety] Approval timed out for %s", experiment_id)
        return False

    def approve(self, experiment_id: str) -> None:
        """Approve an experiment (called from the API layer)."""
        self._redis.set(f"chaos:approval:{experiment_id}", "approved", ex=600)

    def reject(self, experiment_id: str) -> None:
        """Reject an experiment."""
        self._redis.set(f"chaos:approval:{experiment_id}", "rejected", ex=600)

    def is_aborted(self, scan_id: str) -> bool:
        """Check if an emergency stop has been triggered."""
        return self._redis.get(f"chaos:kill:{scan_id}") == "1"

    def trigger_emergency_stop(self, scan_id: str) -> None:
        """Trigger emergency stop for all experiments in a scan."""
        self._redis.set(f"chaos:kill:{scan_id}", "1", ex=600)
        logger.warning("[safety] EMERGENCY STOP triggered for scan %s", scan_id)

    def clear_emergency_stop(self, scan_id: str) -> None:
        """Clear the kill switch after cleanup."""
        self._redis.delete(f"chaos:kill:{scan_id}")

    def set_active_experiment(self, scan_id: str, experiment_id: str) -> bool:
        """Attempt to set this as the active experiment. Returns False if one is already running."""
        key = f"chaos:active:{scan_id}"
        result = self._redis.set(key, experiment_id, nx=True, ex=self.limits.max_experiment_duration_s + 60)
        return bool(result)

    def clear_active_experiment(self, scan_id: str) -> None:
        """Release the active experiment lock."""
        self._redis.delete(f"chaos:active:{scan_id}")
