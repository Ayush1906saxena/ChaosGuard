"""Race condition probe agent.

Tests concurrent request handling to identify TOCTOU and other
race condition vulnerabilities.
"""
import asyncio
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

CONCURRENCY = 10


class RaceConditionAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Focus on state-changing endpoints (POST/PUT/DELETE)
        state_routes = [r for r in self.routes if r.get("method", "GET") in ("POST", "PUT", "DELETE")]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in state_routes[:5]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "POST")

                # Replace path params with test values
                for param in route.get("params", []):
                    path = path.replace(f"{{{param}}}", "1")
                    path = path.replace(f":{param}", "1")

                url = f"{self.target_url}{path}"

                # Send concurrent requests
                async def make_request():
                    if not self.safety.can_make_request():
                        return None
                    await self.safety.rate_limit()
                    try:
                        resp = await client.request(method, url, json={"test": "race"})
                        self.safety.log_request(method, url, resp.status_code, "concurrent")
                        return resp.status_code
                    except Exception:
                        return None

                tasks = [make_request() for _ in range(CONCURRENCY)]
                results = await asyncio.gather(*tasks)
                statuses = [r for r in results if r is not None]

                # If all concurrent requests succeeded, potential race condition
                success_count = sum(1 for s in statuses if 200 <= s < 300)
                if success_count > 1 and method in ("POST", "PUT"):
                    findings.append({
                        "title": f"Potential race condition on {route['path']}",
                        "severity": "MEDIUM",
                        "category": "race_condition",
                        "subcategory": "toctou",
                        "description": (
                            f"{success_count}/{len(statuses)} concurrent {method} requests to "
                            f"{route['path']} succeeded. This may indicate missing concurrency controls."
                        ),
                        "evidence": f"Concurrent requests: {len(statuses)}, Successes: {success_count}",
                        "file_path": route.get("file", ""),
                        "confidence": 0.5,
                    })

        return {"findings": findings}
