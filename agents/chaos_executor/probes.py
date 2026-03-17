"""Health Probing — discovers health endpoints and probes them during chaos."""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

COMMON_HEALTH_PATHS = [
    "/health", "/healthz", "/api/health", "/actuator/health",
    "/ready", "/readyz", "/status", "/ping", "/",
]


@dataclass
class ProbeTarget:
    service: str
    url: str
    method: str = "GET"


@dataclass
class ProbeResult:
    timestamp: str
    service: str
    url: str
    status_code: int
    response_time_ms: float
    success: bool
    error: str = ""


class HealthProber:
    """Discovers and probes health endpoints."""

    async def discover_endpoints(
        self, clone_path: str, exposed_ports: dict[str, list[int]]
    ) -> list[ProbeTarget]:
        """Auto-discover health endpoints from ports and code patterns."""
        targets: list[ProbeTarget] = []

        for service, ports in exposed_ports.items():
            for port in ports:
                # Try common health paths
                best = await self._find_working_endpoint(port)
                if best:
                    targets.append(ProbeTarget(service=service, url=best))
                else:
                    # Fall back to TCP on the port
                    targets.append(ProbeTarget(
                        service=service,
                        url=f"http://localhost:{port}/",
                    ))

        if not targets:
            logger.warning("[probes] No health endpoints discovered")

        return targets

    async def probe_once(self, targets: list[ProbeTarget]) -> list[ProbeResult]:
        """Probe all targets once and return results."""
        results = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            for target in targets:
                result = await self._probe_single(client, target)
                results.append(result)
        return results

    async def probe_continuously(
        self, targets: list[ProbeTarget], duration_s: float, interval_s: float = 2.0
    ) -> list[ProbeResult]:
        """Probe targets continuously for a duration, returning all results."""
        all_results: list[ProbeResult] = []
        deadline = time.time() + duration_s

        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            while time.time() < deadline:
                for target in targets:
                    result = await self._probe_single(client, target)
                    all_results.append(result)
                await asyncio.sleep(interval_s)

        return all_results

    async def _probe_single(self, client: httpx.AsyncClient, target: ProbeTarget) -> ProbeResult:
        """Probe a single endpoint."""
        start = time.time()
        try:
            resp = await client.request(target.method, target.url)
            elapsed_ms = (time.time() - start) * 1000
            return ProbeResult(
                timestamp=datetime.utcnow().isoformat(),
                service=target.service,
                url=target.url,
                status_code=resp.status_code,
                response_time_ms=round(elapsed_ms, 1),
                success=200 <= resp.status_code < 500,
            )
        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            return ProbeResult(
                timestamp=datetime.utcnow().isoformat(),
                service=target.service,
                url=target.url,
                status_code=0,
                response_time_ms=round(elapsed_ms, 1),
                success=False,
                error=str(exc)[:200],
            )

    async def _find_working_endpoint(self, port: int) -> str | None:
        """Try common health paths and return the first 2xx one."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            for path in COMMON_HEALTH_PATHS:
                url = f"http://localhost:{port}{path}"
                try:
                    resp = await client.get(url)
                    if 200 <= resp.status_code < 400:
                        logger.info("[probes] Found health endpoint: %s -> %d", url, resp.status_code)
                        return url
                except Exception:
                    continue
        return None
