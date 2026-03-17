"""Sandbox Orchestrator — spins up the scanned repo's Docker Compose stack
in an isolated network, applies safety limits, and tears it down."""

import asyncio
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)

SANDBOX_PREFIX = "cg-sandbox"
MAX_CONTAINER_CPU = "1.0"
MAX_CONTAINER_MEM = "512m"
PROVISION_TIMEOUT = 180  # seconds
HARD_TIMEOUT = 600  # 10-minute absolute max


@dataclass
class SandboxState:
    scan_id: str
    project_name: str
    compose_path: str
    work_dir: str
    network_name: str
    services: list[str] = field(default_factory=list)
    container_ids: dict[str, str] = field(default_factory=dict)
    is_running: bool = False


class SandboxOrchestrator:
    """Manages the lifecycle of a sandboxed Docker Compose application."""

    # Dangerous compose options that we strip for safety
    BLOCKED_OPTIONS = {
        "privileged", "cap_add", "cap_drop", "security_opt",
        "pid", "ipc", "cgroup_parent", "devices",
    }

    def find_compose_file(self, clone_path: str) -> str | None:
        """Find docker-compose file in the cloned repo."""
        candidates = [
            "docker-compose.yml", "docker-compose.yaml",
            "compose.yml", "compose.yaml",
        ]
        for name in candidates:
            path = os.path.join(clone_path, name)
            if os.path.isfile(path):
                return path
        return None

    async def provision(self, scan_id: str, clone_path: str) -> SandboxState:
        """Parse, sanitise, and start the target application in isolation."""
        compose_src = self.find_compose_file(clone_path)
        if not compose_src:
            raise FileNotFoundError("No docker-compose.yml found in repo")

        with open(compose_src) as f:
            compose_data = yaml.safe_load(f)

        if not compose_data or "services" not in compose_data:
            raise ValueError("Invalid compose file: no services defined")

        short_id = scan_id[:8]
        project_name = f"{SANDBOX_PREFIX}-{short_id}"
        network_name = f"{project_name}-net"

        # Create a temp working directory for the sanitised compose file
        work_dir = tempfile.mkdtemp(prefix=f"cg_sandbox_{short_id}_")

        # Copy the repo into the work dir so build contexts resolve
        repo_copy = os.path.join(work_dir, "repo")
        shutil.copytree(clone_path, repo_copy, dirs_exist_ok=True)

        sanitised = self._sanitise_compose(compose_data, project_name, network_name)
        compose_path = os.path.join(repo_copy, "docker-compose.yml")
        with open(compose_path, "w") as f:
            yaml.dump(sanitised, f, default_flow_style=False)

        services = list(sanitised.get("services", {}).keys())

        state = SandboxState(
            scan_id=scan_id,
            project_name=project_name,
            compose_path=compose_path,
            work_dir=work_dir,
            network_name=network_name,
            services=services,
        )

        # Start the stack
        logger.info("[sandbox] Provisioning %s with %d services", project_name, len(services))
        await self._compose_up(state)
        state.is_running = True

        # Discover container IDs
        state.container_ids = await self._discover_containers(state)
        logger.info("[sandbox] Containers: %s", state.container_ids)

        return state

    async def wait_ready(self, state: SandboxState, timeout_s: int = 120) -> bool:
        """Wait for at least one container to be running."""
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            ids = await self._discover_containers(state)
            if ids:
                state.container_ids = ids
                running = await self._count_running(state)
                if running > 0:
                    logger.info("[sandbox] %d/%d containers running", running, len(state.services))
                    return True
            await asyncio.sleep(3)
        return False

    async def teardown(self, state: SandboxState) -> None:
        """Destroy all sandbox containers and clean up."""
        logger.info("[sandbox] Tearing down %s", state.project_name)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", state.compose_path,
                "-p", state.project_name,
                "down", "-v", "--remove-orphans", "--timeout", "10",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.join(state.work_dir, "repo"),
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
        except Exception as exc:
            logger.warning("[sandbox] Teardown compose error: %s", exc)

        # Force-kill any remaining containers with our prefix
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={state.project_name}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            container_ids = stdout.decode().strip().split()
            for cid in container_ids:
                if cid:
                    await asyncio.create_subprocess_exec("docker", "rm", "-f", cid)
        except Exception:
            pass

        # Remove the network
        try:
            await asyncio.create_subprocess_exec("docker", "network", "rm", state.network_name)
        except Exception:
            pass

        # Clean work dir
        if state.work_dir and os.path.exists(state.work_dir):
            shutil.rmtree(state.work_dir, ignore_errors=True)

        state.is_running = False
        logger.info("[sandbox] Teardown complete for %s", state.project_name)

    async def get_service_ip(self, state: SandboxState, service: str) -> str | None:
        """Get the IP address of a service container on the sandbox network."""
        cid = state.container_ids.get(service)
        if not cid:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                cid,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            ip = stdout.decode().strip()
            return ip if ip else None
        except Exception:
            return None

    async def get_exposed_ports(self, state: SandboxState) -> dict[str, list[int]]:
        """Get host-mapped ports for each service."""
        result: dict[str, list[int]] = {}
        for svc, cid in state.container_ids.items():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "port", cid,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                ports = []
                for line in stdout.decode().strip().split("\n"):
                    if "->" in line:
                        host_part = line.split("->")[-1].strip()
                        port = int(host_part.split(":")[-1])
                        ports.append(port)
                if ports:
                    result[svc] = ports
            except Exception:
                pass
        return result

    # ── Internal helpers ──────────────────────────────────────────────

    def _sanitise_compose(self, data: dict, project_name: str, network_name: str) -> dict:
        """Strip dangerous options, add resource limits, isolate network."""
        sanitised = {"version": "3.8", "services": {}, "networks": {
            "sandbox": {"driver": "bridge", "name": network_name}
        }}

        for svc_name, svc_conf in data.get("services", {}).items():
            clean = dict(svc_conf)

            # Remove dangerous options
            for key in self.BLOCKED_OPTIONS:
                clean.pop(key, None)

            # Force network mode to our sandbox
            clean.pop("network_mode", None)
            clean.pop("networks", None)
            clean["networks"] = ["sandbox"]

            # Strip host port mappings — remap to random available ports
            if "ports" in clean:
                new_ports = []
                for p in clean["ports"]:
                    p_str = str(p)
                    # "8080:8080" -> "8080" (let Docker pick host port)
                    if ":" in p_str:
                        container_port = p_str.split(":")[-1]
                        new_ports.append(container_port)
                    else:
                        new_ports.append(p_str)
                clean["ports"] = new_ports

            # Add resource limits
            clean["deploy"] = {
                "resources": {
                    "limits": {"cpus": MAX_CONTAINER_CPU, "memory": MAX_CONTAINER_MEM}
                }
            }

            # Strip volumes that mount host paths
            if "volumes" in clean:
                safe_volumes = []
                for v in clean["volumes"]:
                    v_str = str(v)
                    # Keep named volumes and relative paths, strip absolute host paths
                    if v_str.startswith("/") and ":" in v_str:
                        continue  # absolute host path mount — skip
                    safe_volumes.append(v)
                clean["volumes"] = safe_volumes

            sanitised["services"][svc_name] = clean

        return sanitised

    async def _compose_up(self, state: SandboxState) -> None:
        """Run docker compose up -d."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", state.compose_path,
            "-p", state.project_name,
            "up", "-d", "--build", "--remove-orphans",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.join(state.work_dir, "repo"),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=PROVISION_TIMEOUT)
        if proc.returncode != 0:
            error = stderr.decode()[-2000:]
            raise RuntimeError(f"docker compose up failed: {error}")

    async def _discover_containers(self, state: SandboxState) -> dict[str, str]:
        """Map service names to container IDs."""
        result = {}
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", state.compose_path,
            "-p", state.project_name, "ps", "-q",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=os.path.join(state.work_dir, "repo"),
        )
        stdout, _ = await proc.communicate()
        container_ids = [c.strip() for c in stdout.decode().strip().split("\n") if c.strip()]

        for cid in container_ids:
            proc2 = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f",
                "{{index .Config.Labels \"com.docker.compose.service\"}}",
                cid,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await proc2.communicate()
            svc = out.decode().strip()
            if svc:
                result[svc] = cid

        return result

    async def _count_running(self, state: SandboxState) -> int:
        """Count containers in running state."""
        count = 0
        for cid in state.container_ids.values():
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f", "{{.State.Running}}", cid,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            if out.decode().strip() == "true":
                count += 1
        return count
