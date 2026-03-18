"""Tests for SandboxOrchestrator (agents/chaos_executor/sandbox.py).

Covers compose-file sanitization (privileged removal, resource limits,
port remapping, volume filtering, network forcing) and teardown/discovery.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chaos_executor.sandbox import SandboxOrchestrator, SandboxState


@pytest.fixture
def orchestrator():
    return SandboxOrchestrator()


@pytest.fixture
def raw_compose():
    """A realistic but unsafe docker-compose data dict."""
    return {
        "version": "3.8",
        "services": {
            "web": {
                "image": "myapp:latest",
                "privileged": True,
                "cap_add": ["NET_ADMIN"],
                "security_opt": ["seccomp:unconfined"],
                "ports": ["8080:8080", "9090:9090"],
                "volumes": [
                    "/var/run/docker.sock:/var/run/docker.sock",
                    "./data:/app/data",
                    "db-data:/var/lib/db",
                ],
                "networks": ["external"],
                "network_mode": "host",
            },
            "db": {
                "image": "postgres:15",
                "privileged": False,
                "devices": ["/dev/sda"],
                "ports": ["5432:5432"],
                "volumes": ["pg-data:/var/lib/postgresql/data"],
            },
        },
    }


@pytest.fixture
def sandbox_state():
    return SandboxState(
        scan_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        project_name="cg-sandbox-aaaaaaaa",
        compose_path="/tmp/cg_sandbox/repo/docker-compose.yml",
        work_dir="/tmp/cg_sandbox",
        network_name="cg-sandbox-aaaaaaaa-net",
        services=["web", "db"],
        container_ids={"web": "cid-web-111", "db": "cid-db-222"},
        is_running=True,
    )


# ── Sanitization tests ──────────────────────────────────────────────


class TestSanitizeCompose:
    def test_sanitize_removes_privileged(self, orchestrator, raw_compose):
        """Sanitization must strip 'privileged', 'cap_add', 'security_opt', 'devices'."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "net")
        web = result["services"]["web"]
        db = result["services"]["db"]

        for key in ("privileged", "cap_add", "security_opt", "devices"):
            assert key not in web, f"'{key}' should be removed from web"
            assert key not in db, f"'{key}' should be removed from db"

    def test_sanitize_adds_resource_limits(self, orchestrator, raw_compose):
        """Every service should have deploy.resources.limits with cpu and memory."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "net")
        for svc_name, svc in result["services"].items():
            assert "deploy" in svc, f"{svc_name} missing deploy"
            limits = svc["deploy"]["resources"]["limits"]
            assert "cpus" in limits
            assert "memory" in limits

    def test_sanitize_removes_host_port_bindings(self, orchestrator, raw_compose):
        """Host:container port mappings should be stripped to container-only ports."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "net")
        web_ports = result["services"]["web"]["ports"]
        for p in web_ports:
            assert ":" not in str(p), f"Port '{p}' still has host binding"

    def test_sanitize_removes_absolute_volume_mounts(self, orchestrator, raw_compose):
        """Absolute host-path volume mounts (e.g. /var/run/...) should be removed."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "net")
        web_volumes = result["services"]["web"].get("volumes", [])
        for v in web_volumes:
            if ":" in str(v):
                assert not str(v).startswith("/"), (
                    f"Absolute volume mount '{v}' was not removed"
                )

    def test_sanitize_keeps_named_volumes(self, orchestrator, raw_compose):
        """Named volumes (e.g. 'db-data:/var/lib/db') should be preserved."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "net")
        web_volumes = result["services"]["web"].get("volumes", [])
        named = [str(v) for v in web_volumes if not str(v).startswith("/") and not str(v).startswith(".")]
        assert any("db-data" in v for v in named), "Named volume 'db-data' should be kept"

    def test_sanitize_forces_bridge_network(self, orchestrator, raw_compose):
        """All services should be moved to a sandbox bridge network."""
        result = orchestrator._sanitise_compose(raw_compose, "proj", "mynet")

        # Top-level networks should have a bridge driver
        assert "sandbox" in result["networks"]
        assert result["networks"]["sandbox"]["driver"] == "bridge"

        # Each service should only be on the sandbox network
        for svc_name, svc in result["services"].items():
            assert svc["networks"] == ["sandbox"], (
                f"{svc_name} not forced to sandbox network"
            )
            assert "network_mode" not in svc


# ── Teardown ─────────────────────────────────────────────────────────


class TestTeardown:
    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @patch("shutil.rmtree")
    @patch("os.path.exists", return_value=True)
    async def test_teardown_calls_compose_down(
        self, mock_exists, mock_rmtree, mock_subproc, orchestrator, sandbox_state
    ):
        """Teardown should invoke 'docker compose down' and clean up the work dir."""
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc

        await orchestrator.teardown(sandbox_state)

        assert sandbox_state.is_running is False
        # Verify compose down was called
        first_call_args = mock_subproc.call_args_list[0]
        cmd_parts = first_call_args[0]
        assert "down" in cmd_parts


# ── Container discovery ──────────────────────────────────────────────


class TestContainerDiscovery:
    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    async def test_container_discovery(self, mock_subproc, orchestrator, sandbox_state):
        """_discover_containers should map service names to container IDs."""
        # First call: docker compose ps -q returns container IDs
        mock_ps = AsyncMock()
        mock_ps.communicate = AsyncMock(return_value=(b"cid-001\ncid-002\n", b""))

        # Subsequent calls: docker inspect returns service labels
        mock_inspect_web = AsyncMock()
        mock_inspect_web.communicate = AsyncMock(return_value=(b"web\n", b""))
        mock_inspect_db = AsyncMock()
        mock_inspect_db.communicate = AsyncMock(return_value=(b"db\n", b""))

        mock_subproc.side_effect = [mock_ps, mock_inspect_web, mock_inspect_db]

        result = await orchestrator._discover_containers(sandbox_state)
        assert result == {"web": "cid-001", "db": "cid-002"}
