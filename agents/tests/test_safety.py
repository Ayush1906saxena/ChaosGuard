"""Tests for SafetyController (agents/chaos_executor/safety.py).

Covers blast-radius validation, duration validation, approval workflows,
emergency stop, experiment locking, and env-var overrides.
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

# Patch redis and config before importing the module under test
_mock_redis_cls = MagicMock()
_mock_config = MagicMock()
_mock_config.REDIS_URL = "redis://localhost:6379"


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Patch redis.Redis.from_url and config for every test in this module."""
    import redis as _redis_mod

    monkeypatch.setattr(_redis_mod.Redis, "from_url", lambda *a, **kw: MagicMock())


def _make_controller(limits_kw=None):
    """Create a SafetyController with a mocked Redis backend."""
    with patch("chaos_executor.safety.config", _mock_config):
        from chaos_executor.safety import SafetyController, SafetyLimits

        limits = SafetyLimits(**(limits_kw or {}))
        ctrl = SafetyController(limits=limits)
    return ctrl


# ── Blast-radius validation ──────────────────────────────────────────


class TestValidateBlastRadius:
    def test_validate_blast_radius_within_limit(self, sample_experiment_config):
        """Experiment affecting 2 services should pass the default limit of 3."""
        ctrl = _make_controller()
        errors = ctrl.validate_experiment(sample_experiment_config)
        blast_errors = [e for e in errors if "Blast radius" in e]
        assert blast_errors == []

    def test_validate_blast_radius_exceeds_limit(self, oversized_experiment_config):
        """Experiment affecting 5 services should fail the default limit of 3."""
        ctrl = _make_controller()
        errors = ctrl.validate_experiment(oversized_experiment_config)
        blast_errors = [e for e in errors if "Blast radius" in e]
        assert len(blast_errors) == 1
        assert "exceeds limit" in blast_errors[0]


# ── Duration validation ──────────────────────────────────────────────


class TestValidateDuration:
    def test_validate_duration_within_limit(self, sample_experiment_config):
        """120s experiment should pass the default 300s limit."""
        ctrl = _make_controller()
        errors = ctrl.validate_experiment(sample_experiment_config)
        dur_errors = [e for e in errors if "Duration" in e]
        assert dur_errors == []

    def test_validate_duration_exceeds_limit(self):
        """600s experiment should fail the default 300s limit."""
        ctrl = _make_controller()
        plan = {
            "faults": [{"target_service": "api", "fault_type": "delay", "params": {}}],
            "total_duration_s": 600,
        }
        errors = ctrl.validate_experiment(plan)
        dur_errors = [e for e in errors if "Duration" in e]
        assert len(dur_errors) == 1
        assert "exceeds limit" in dur_errors[0]


# ── Approval workflow ────────────────────────────────────────────────


class TestRequestApproval:
    @pytest.mark.asyncio
    async def test_request_approval_approved(self, experiment_id):
        """When Redis returns 'approved', request_approval should return True."""
        ctrl = _make_controller()
        ctrl._redis.get.return_value = "approved"
        result = await ctrl.request_approval(experiment_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_request_approval_rejected(self, experiment_id):
        """When Redis returns 'rejected', request_approval should return False."""
        ctrl = _make_controller()
        ctrl._redis.get.return_value = "rejected"
        result = await ctrl.request_approval(experiment_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_request_approval_timeout(self, experiment_id):
        """When no approval arrives before the deadline, should return False."""
        ctrl = _make_controller({"require_approval": True, "approval_timeout_s": 1})
        ctrl._redis.get.return_value = None  # never approved
        result = await ctrl.request_approval(experiment_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_request_approval_skipped_when_not_required(self, experiment_id):
        """When require_approval is False, should return True immediately."""
        ctrl = _make_controller({"require_approval": False})
        result = await ctrl.request_approval(experiment_id)
        assert result is True


# ── Emergency stop ───────────────────────────────────────────────────


class TestEmergencyStop:
    def test_emergency_stop_sets_kill_key(self, scan_id):
        """trigger_emergency_stop should set the kill key in Redis."""
        ctrl = _make_controller()
        ctrl.trigger_emergency_stop(scan_id)
        ctrl._redis.set.assert_called_once_with(
            f"chaos:kill:{scan_id}", "1", ex=600
        )

    def test_check_abort_returns_true_when_killed(self, scan_id):
        """is_aborted should return True when the kill key is '1'."""
        ctrl = _make_controller()
        ctrl._redis.get.return_value = "1"
        assert ctrl.is_aborted(scan_id) is True

    def test_check_abort_returns_false_normally(self, scan_id):
        """is_aborted should return False when no kill key is set."""
        ctrl = _make_controller()
        ctrl._redis.get.return_value = None
        assert ctrl.is_aborted(scan_id) is False


# ── Experiment locking ───────────────────────────────────────────────


class TestExperimentLock:
    def test_acquire_experiment_lock_success(self, scan_id, experiment_id):
        """set_active_experiment should return True when nx-set succeeds."""
        ctrl = _make_controller()
        ctrl._redis.set.return_value = True  # nx succeeded
        assert ctrl.set_active_experiment(scan_id, experiment_id) is True

    def test_acquire_experiment_lock_already_held(self, scan_id, experiment_id):
        """set_active_experiment should return False when another experiment holds the lock."""
        ctrl = _make_controller()
        ctrl._redis.set.return_value = None  # nx failed
        assert ctrl.set_active_experiment(scan_id, experiment_id) is False


# ── Configurable limits from environment ─────────────────────────────


class TestConfigurableLimits:
    def test_configurable_limits_from_env(self):
        """SafetyLimits should accept custom values that override defaults."""
        from chaos_executor.safety import SafetyLimits

        custom = SafetyLimits(
            max_blast_radius=10,
            max_experiment_duration_s=900,
            max_concurrent_experiments=5,
        )
        assert custom.max_blast_radius == 10
        assert custom.max_experiment_duration_s == 900
        assert custom.max_concurrent_experiments == 5

    def test_controller_uses_custom_limits(self):
        """SafetyController should respect the custom limits passed in."""
        ctrl = _make_controller({"max_blast_radius": 10, "max_experiment_duration_s": 900})
        plan = {
            "faults": [
                {"target_service": f"svc-{i}", "fault_type": "delay", "params": {}}
                for i in range(8)
            ],
            "total_duration_s": 800,
        }
        errors = ctrl.validate_experiment(plan)
        assert errors == []
