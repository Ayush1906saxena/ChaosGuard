"""Fault Injectors — concrete chaos primitives executed via Docker API.

Every injector records its rollback command so cleanup is always possible.
Network faults use a nicolaka/netshoot sidecar sharing the target's
network namespace so tc/iptables are always available.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

NETSHOOT_IMAGE = "nicolaka/netshoot:latest"


@dataclass
class InjectionResult:
    injection_id: str
    fault_type: str
    target_container: str
    target_service: str
    params: dict
    success: bool
    started_at: str
    error: str = ""
    sidecar_id: str = ""  # for network faults


@dataclass
class RollbackEntry:
    injection_id: str
    rollback_cmd: list[str]
    sidecar_id: str = ""


class FaultInjector(ABC):
    fault_type: str = "unknown"

    @abstractmethod
    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        ...

    @abstractmethod
    async def rollback(self, result: InjectionResult) -> None:
        ...


# ── Helper ────────────────────────────────────────────────────────────

async def _exec(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "timeout"


async def _start_netshoot_sidecar(target_container_id: str, injection_id: str) -> str:
    """Launch a netshoot container sharing the target's network namespace."""
    sidecar_name = f"cg-netshoot-{injection_id[:12]}"
    rc, stdout, stderr = await _exec([
        "docker", "run", "-d", "--rm",
        "--name", sidecar_name,
        f"--network=container:{target_container_id}",
        "--cap-add=NET_ADMIN",
        NETSHOOT_IMAGE,
        "sleep", "3600",
    ])
    if rc != 0:
        raise RuntimeError(f"Failed to start netshoot sidecar: {stderr}")
    return stdout.strip()


async def _stop_sidecar(sidecar_id: str) -> None:
    """Stop and remove a sidecar container."""
    if sidecar_id:
        await _exec(["docker", "rm", "-f", sidecar_id], timeout=10)


# ── Network Fault Injectors ──────────────────────────────────────────

class NetworkDelayInjector(FaultInjector):
    """Adds network latency to a container using tc netem."""
    fault_type = "network_delay"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        delay_ms = params.get("delay_ms", 500)
        jitter_ms = params.get("jitter_ms", 100)

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            sidecar_id = await _start_netshoot_sidecar(container_id, injection_id)
            result.sidecar_id = sidecar_id

            rc, _, err = await _exec([
                "docker", "exec", sidecar_id,
                "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
                "delay", f"{delay_ms}ms", f"{jitter_ms}ms",
            ])
            if rc != 0:
                result.error = f"tc failed: {err}"
                await _stop_sidecar(sidecar_id)
                return result

            result.success = True
            logger.info("[inject] Network delay %dms±%dms on %s", delay_ms, jitter_ms, service_name)

        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        if result.sidecar_id:
            await _exec([
                "docker", "exec", result.sidecar_id,
                "tc", "qdisc", "del", "dev", "eth0", "root",
            ], timeout=10)
            await _stop_sidecar(result.sidecar_id)
            logger.info("[rollback] Removed network delay from %s", result.target_service)


class NetworkPartitionInjector(FaultInjector):
    """Drops all traffic between two containers using iptables."""
    fault_type = "network_partition"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        target_ip = params.get("target_ip", "")

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        if not target_ip:
            result.error = "target_ip required"
            return result

        try:
            sidecar_id = await _start_netshoot_sidecar(container_id, injection_id)
            result.sidecar_id = sidecar_id

            rc, _, err = await _exec([
                "docker", "exec", sidecar_id,
                "iptables", "-A", "OUTPUT", "-d", target_ip, "-j", "DROP",
            ])
            if rc != 0:
                result.error = f"iptables failed: {err}"
                await _stop_sidecar(sidecar_id)
                return result

            # Also block incoming
            await _exec([
                "docker", "exec", sidecar_id,
                "iptables", "-A", "INPUT", "-s", target_ip, "-j", "DROP",
            ])

            result.success = True
            logger.info("[inject] Network partition: %s <-/-> %s", service_name, target_ip)

        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        if result.sidecar_id:
            target_ip = result.params.get("target_ip", "")
            if target_ip:
                await _exec([
                    "docker", "exec", result.sidecar_id,
                    "iptables", "-D", "OUTPUT", "-d", target_ip, "-j", "DROP",
                ], timeout=10)
                await _exec([
                    "docker", "exec", result.sidecar_id,
                    "iptables", "-D", "INPUT", "-s", target_ip, "-j", "DROP",
                ], timeout=10)
            await _stop_sidecar(result.sidecar_id)
            logger.info("[rollback] Removed network partition from %s", result.target_service)


class PacketLossInjector(FaultInjector):
    """Introduces packet loss using tc netem."""
    fault_type = "packet_loss"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        loss_percent = params.get("loss_percent", 30)

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            sidecar_id = await _start_netshoot_sidecar(container_id, injection_id)
            result.sidecar_id = sidecar_id

            rc, _, err = await _exec([
                "docker", "exec", sidecar_id,
                "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
                "loss", f"{loss_percent}%",
            ])
            if rc != 0:
                result.error = f"tc failed: {err}"
                await _stop_sidecar(sidecar_id)
                return result

            result.success = True
            logger.info("[inject] %d%% packet loss on %s", loss_percent, service_name)

        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        if result.sidecar_id:
            await _exec([
                "docker", "exec", result.sidecar_id,
                "tc", "qdisc", "del", "dev", "eth0", "root",
            ], timeout=10)
            await _stop_sidecar(result.sidecar_id)
            logger.info("[rollback] Removed packet loss from %s", result.target_service)


# ── Container Lifecycle Injectors ─────────────────────────────────────

class ContainerKillInjector(FaultInjector):
    """Kills a container (simulates process crash)."""
    fault_type = "container_kill"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        signal = params.get("signal", "SIGKILL")

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            rc, _, err = await _exec(["docker", "kill", f"--signal={signal}", container_id])
            result.success = rc == 0
            if not result.success:
                result.error = err
            else:
                logger.info("[inject] Killed container %s (%s) with %s", service_name, container_id[:12], signal)
        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        # Restart the container
        await _exec(["docker", "start", result.target_container], timeout=30)
        logger.info("[rollback] Restarted container %s", result.target_service)


class ContainerPauseInjector(FaultInjector):
    """Pauses a container (simulates freeze / GC stop-the-world)."""
    fault_type = "container_pause"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            rc, _, err = await _exec(["docker", "pause", container_id])
            result.success = rc == 0
            if not result.success:
                result.error = err
            else:
                logger.info("[inject] Paused container %s (%s)", service_name, container_id[:12])
        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        await _exec(["docker", "unpause", result.target_container], timeout=10)
        logger.info("[rollback] Unpaused container %s", result.target_service)


# ── Resource Stress Injectors ─────────────────────────────────────────

class CpuStressInjector(FaultInjector):
    """Stresses CPU inside a container using dd/yes."""
    fault_type = "cpu_stress"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        duration_s = params.get("duration_s", 30)
        cores = params.get("cores", 2)

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            # Use shell-based CPU stress that works in any container
            stress_cmd = " & ".join(
                [f"(timeout {duration_s} yes > /dev/null 2>&1 &)"] * cores
            )
            rc, _, err = await _exec([
                "docker", "exec", "-d", container_id,
                "sh", "-c", stress_cmd,
            ])
            result.success = rc == 0
            if not result.success:
                result.error = err
            else:
                logger.info("[inject] CPU stress (%d cores, %ds) on %s", cores, duration_s, service_name)
        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        # Kill stress processes
        await _exec([
            "docker", "exec", result.target_container,
            "sh", "-c", "pkill -f 'yes' 2>/dev/null; true",
        ], timeout=10)
        logger.info("[rollback] Stopped CPU stress on %s", result.target_service)


class MemoryStressInjector(FaultInjector):
    """Allocates memory inside a container."""
    fault_type = "memory_stress"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        mb = params.get("mb", 256)
        duration_s = params.get("duration_s", 30)

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            # Allocate memory using dd to tmpfs
            rc, _, err = await _exec([
                "docker", "exec", "-d", container_id,
                "sh", "-c",
                f"dd if=/dev/zero of=/tmp/chaos_mem bs=1M count={mb} 2>/dev/null; "
                f"sleep {duration_s}; rm -f /tmp/chaos_mem",
            ])
            result.success = rc == 0
            if not result.success:
                result.error = err
            else:
                logger.info("[inject] Memory stress (%dMB, %ds) on %s", mb, duration_s, service_name)
        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        await _exec([
            "docker", "exec", result.target_container,
            "sh", "-c", "rm -f /tmp/chaos_mem 2>/dev/null; true",
        ], timeout=10)
        logger.info("[rollback] Freed memory stress on %s", result.target_service)


# ── DiskFill Injector ─────────────────────────────────────────────────

class DiskFillInjector(FaultInjector):
    """Fills disk space inside a container."""
    fault_type = "disk_fill"

    async def inject(self, container_id: str, service_name: str, params: dict) -> InjectionResult:
        injection_id = str(uuid.uuid4())[:8]
        mb = params.get("mb", 100)

        result = InjectionResult(
            injection_id=injection_id, fault_type=self.fault_type,
            target_container=container_id, target_service=service_name,
            params=params, success=False, started_at=datetime.utcnow().isoformat(),
        )

        try:
            rc, _, err = await _exec([
                "docker", "exec", container_id,
                "sh", "-c",
                f"dd if=/dev/zero of=/tmp/chaos_diskfill bs=1M count={mb} 2>/dev/null",
            ])
            result.success = rc == 0
            if not result.success:
                result.error = err
            else:
                logger.info("[inject] Disk fill %dMB on %s", mb, service_name)
        except Exception as exc:
            result.error = str(exc)

        return result

    async def rollback(self, result: InjectionResult) -> None:
        await _exec([
            "docker", "exec", result.target_container,
            "sh", "-c", "rm -f /tmp/chaos_diskfill 2>/dev/null; true",
        ], timeout=10)
        logger.info("[rollback] Removed disk fill from %s", result.target_service)


# ── Registry ──────────────────────────────────────────────────────────

INJECTOR_REGISTRY: dict[str, FaultInjector] = {
    "network_delay": NetworkDelayInjector(),
    "network_partition": NetworkPartitionInjector(),
    "packet_loss": PacketLossInjector(),
    "container_kill": ContainerKillInjector(),
    "container_pause": ContainerPauseInjector(),
    "cpu_stress": CpuStressInjector(),
    "memory_stress": MemoryStressInjector(),
    "disk_fill": DiskFillInjector(),
}
