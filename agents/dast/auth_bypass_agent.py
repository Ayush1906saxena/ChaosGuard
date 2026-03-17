"""Authentication bypass probe agent.

Tests endpoints without authentication tokens or with malformed tokens.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)


class AuthBypassAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []
        auth_routes = [r for r in self.routes if r.get("auth_required")]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in auth_routes[:15]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")
                # Replace path params with test values
                for param in route.get("params", []):
                    path = path.replace(f"{{{param}}}", "1")
                    path = path.replace(f":{param}", "1")

                url = f"{self.target_url}{path}"

                # Test 1: No auth header at all
                try:
                    await self.safety.rate_limit()
                    resp = await client.request(method, url)
                    self.safety.log_request(method, url, resp.status_code)

                    if resp.status_code == 200:
                        findings.append({
                            "title": f"Auth bypass: {path} accessible without token",
                            "severity": "CRITICAL",
                            "category": "authentication",
                            "subcategory": "auth_bypass",
                            "description": f"Endpoint {route['path']} marked as auth-required but accessible without credentials.",
                            "evidence": f"{method} {url} returned {resp.status_code} with no auth",
                            "file_path": route.get("file", ""),
                            "confidence": 0.8,
                        })
                except Exception:
                    pass

                # Test 2: Malformed token
                try:
                    await self.safety.rate_limit()
                    headers = {"Authorization": "Bearer invalid.token.here"}
                    resp = await client.request(method, url, headers=headers)
                    self.safety.log_request(method, url, resp.status_code, "Bearer invalid.token.here")

                    if resp.status_code == 200:
                        findings.append({
                            "title": f"Auth bypass: {path} accepts malformed JWT",
                            "severity": "CRITICAL",
                            "category": "authentication",
                            "subcategory": "jwt_validation",
                            "description": f"Endpoint {route['path']} accepts requests with malformed JWT tokens.",
                            "evidence": f"{method} {url} returned {resp.status_code} with malformed JWT",
                            "file_path": route.get("file", ""),
                            "confidence": 0.85,
                        })
                except Exception:
                    pass

        return {"findings": findings}
