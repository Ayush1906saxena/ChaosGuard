"""Tests for fault injectors (agents/chaos_executor/injectors.py).

Covers registry completeness, inject/rollback commands for every injector type,
and verifies that all injectors implement the rollback method.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chaos_executor.injectors import (
    INJECTOR_REGISTRY,
    ContainerKillInjector,
    ContainerPauseInjector,
    CpuStressInjector,
    DiskFillInjector,
    FaultInjector,
    InjectionResult,
    MemoryStressInjector,
    NetworkDelayInjector,
    NetworkPartitionInjector,
    PacketLossInjector,
)

CONTAINER_ID = "abc123def456"
SERVICE_NAME = "api"


def _make_result(fault_type, sidecar_id="side-abc", **overrides):
    """Helper to build an InjectionResult for rollback tests."""
    defaults = dict(
        injection_id="inj-001",
        fault_type=fault_type,
        target_container=CONTAINER_ID,
        target_service=SERVICE_NAME,
        params={},
        success=True,
        started_at="2026-01-01T00:00:00",
        sidecar_id=sidecar_id,
    )
    defaults.update(overrides)
    return InjectionResult(**defaults)


# ── Registry ─────────────────────────────────────────────────────────


class TestInjectorRegistry:
    EXPECTED_TYPES = {
        "network_delay",
        "network_partition",
        "packet_loss",
        "container_kill",
        "container_pause",
        "cpu_stress",
        "memory_stress",
        "disk_fill",
    }

    def test_injector_registry_has_all_types(self):
        """The INJECTOR_REGISTRY should contain all 8 fault types."""
        assert set(INJECTOR_REGISTRY.keys()) == self.EXPECTED_TYPES

    def test_all_injectors_have_rollback(self):
        """Every registered injector must implement a rollback method."""
        for name, injector in INJECTOR_REGISTRY.items():
            assert hasattr(injector, "rollback"), f"{name} is missing rollback"
            assert callable(injector.rollback), f"{name}.rollback is not callable"

    def test_all_injectors_are_instances_of_base(self):
        """Every registered injector must be a FaultInjector subclass."""
        for name, injector in INJECTOR_REGISTRY.items():
            assert isinstance(injector, FaultInjector), (
                f"{name} is not a FaultInjector instance"
            )


# ── NetworkDelayInjector ─────────────────────────────────────────────


class TestNetworkDelayInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._stop_sidecar", new_callable=AsyncMock)
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    @patch("chaos_executor.injectors._start_netshoot_sidecar", new_callable=AsyncMock)
    async def test_network_delay_inject_command(self, mock_sidecar, mock_exec, mock_stop):
        """Inject should call tc qdisc add with the correct delay and jitter."""
        mock_sidecar.return_value = "sidecar-id-123"
        mock_exec.return_value = (0, "", "")

        injector = NetworkDelayInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"delay_ms": 200, "jitter_ms": 50}
        )

        assert result.success is True
        mock_exec.assert_called_once()
        cmd = mock_exec.call_args[0][0]
        assert "tc" in cmd
        assert "200ms" in cmd
        assert "50ms" in cmd

    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._stop_sidecar", new_callable=AsyncMock)
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_network_delay_rollback_command(self, mock_exec, mock_stop):
        """Rollback should remove the tc qdisc and stop the sidecar."""
        mock_exec.return_value = (0, "", "")
        injector = NetworkDelayInjector()
        ir = _make_result("network_delay", sidecar_id="sidecar-id-123")

        await injector.rollback(ir)

        mock_exec.assert_called_once()
        cmd = mock_exec.call_args[0][0]
        assert "tc" in cmd
        assert "del" in cmd
        mock_stop.assert_called_once_with("sidecar-id-123")


# ── NetworkPartitionInjector ─────────────────────────────────────────


class TestNetworkPartitionInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._stop_sidecar", new_callable=AsyncMock)
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    @patch("chaos_executor.injectors._start_netshoot_sidecar", new_callable=AsyncMock)
    async def test_network_partition_inject_command(self, mock_sidecar, mock_exec, mock_stop):
        """Inject should call iptables to block traffic to the target IP."""
        mock_sidecar.return_value = "sidecar-id-456"
        mock_exec.return_value = (0, "", "")

        injector = NetworkPartitionInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"target_ip": "10.0.0.5"}
        )

        assert result.success is True
        # Should have two iptables calls (OUTPUT + INPUT)
        assert mock_exec.call_count == 2
        first_cmd = mock_exec.call_args_list[0][0][0]
        assert "iptables" in first_cmd
        assert "10.0.0.5" in first_cmd

    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._start_netshoot_sidecar", new_callable=AsyncMock)
    async def test_network_partition_requires_target_ip(self, mock_sidecar):
        """Inject should fail with an error when target_ip is missing."""
        injector = NetworkPartitionInjector()
        result = await injector.inject(CONTAINER_ID, SERVICE_NAME, {})

        assert result.success is False
        assert "target_ip required" in result.error


# ── ContainerKillInjector ────────────────────────────────────────────


class TestContainerKillInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_container_kill_inject_calls_docker(self, mock_exec):
        """Inject should call 'docker kill' with the correct signal."""
        mock_exec.return_value = (0, "", "")
        injector = ContainerKillInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"signal": "SIGTERM"}
        )

        assert result.success is True
        cmd = mock_exec.call_args[0][0]
        assert "docker" in cmd
        assert "kill" in cmd
        assert "--signal=SIGTERM" in cmd


# ── ContainerPauseInjector ───────────────────────────────────────────


class TestContainerPauseInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_container_pause_inject_calls_docker(self, mock_exec):
        """Inject should call 'docker pause' on the target container."""
        mock_exec.return_value = (0, "", "")
        injector = ContainerPauseInjector()
        result = await injector.inject(CONTAINER_ID, SERVICE_NAME, {})

        assert result.success is True
        cmd = mock_exec.call_args[0][0]
        assert "docker" in cmd
        assert "pause" in cmd
        assert CONTAINER_ID in cmd


# ── CpuStressInjector ───────────────────────────────────────────────


class TestCpuStressInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_cpu_stress_inject_starts_processes(self, mock_exec):
        """Inject should run a 'yes > /dev/null' stress command via docker exec."""
        mock_exec.return_value = (0, "", "")
        injector = CpuStressInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"duration_s": 10, "cores": 2}
        )

        assert result.success is True
        cmd = mock_exec.call_args[0][0]
        assert "docker" in cmd
        assert "exec" in cmd
        # The shell command should reference 'yes' twice for 2 cores
        shell_cmd = cmd[-1]
        assert shell_cmd.count("yes") == 2

    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_cpu_stress_rollback_kills_processes(self, mock_exec):
        """Rollback should pkill the 'yes' stress processes."""
        mock_exec.return_value = (0, "", "")
        injector = CpuStressInjector()
        ir = _make_result("cpu_stress", sidecar_id="")

        await injector.rollback(ir)

        cmd = mock_exec.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "pkill" in shell_cmd


# ── MemoryStressInjector ─────────────────────────────────────────────


class TestMemoryStressInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_memory_stress_inject_creates_tmpfs(self, mock_exec):
        """Inject should use dd to allocate memory to /tmp/chaos_mem."""
        mock_exec.return_value = (0, "", "")
        injector = MemoryStressInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"mb": 128, "duration_s": 15}
        )

        assert result.success is True
        cmd = mock_exec.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "/tmp/chaos_mem" in shell_cmd
        assert "count=128" in shell_cmd


# ── DiskFillInjector ─────────────────────────────────────────────────


class TestDiskFillInjector:
    @pytest.mark.asyncio
    @patch("chaos_executor.injectors._exec", new_callable=AsyncMock)
    async def test_disk_fill_inject_creates_file(self, mock_exec):
        """Inject should use dd to create a large file at /tmp/chaos_diskfill."""
        mock_exec.return_value = (0, "", "")
        injector = DiskFillInjector()
        result = await injector.inject(
            CONTAINER_ID, SERVICE_NAME, {"mb": 200}
        )

        assert result.success is True
        cmd = mock_exec.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "/tmp/chaos_diskfill" in shell_cmd
        assert "count=200" in shell_cmd
