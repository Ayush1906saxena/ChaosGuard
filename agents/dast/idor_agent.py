"""IDOR (Insecure Direct Object Reference) probe agent.

Tests sequential ID enumeration on endpoints with path parameters.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)


class IdorAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []
        # Filter routes with ID-like params
        id_routes = [r for r in self.routes if any(
            p.lower() in ("id", "userid", "user_id", "accountid", "account_id", "orderid")
            for p in r.get("params", [])
        )]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in id_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")

                # Replace ID params with sequential values
                for test_id in [1, 2, 3, 9999]:
                    for param in route.get("params", []):
                        test_path = path.replace(f"{{{param}}}", str(test_id))
                        test_path = test_path.replace(f":{param}", str(test_id))

                    url = f"{self.target_url}{test_path}"

                    try:
                        await self.safety.rate_limit()
                        resp = await client.request(method, url)
                        self.safety.log_request(method, url, resp.status_code)

                        if resp.status_code == 200 and test_id == 9999:
                            findings.append({
                                "title": f"Potential IDOR on {path}",
                                "severity": "HIGH",
                                "category": "authorization",
                                "subcategory": "idor",
                                "description": f"Endpoint {path} returns data for arbitrary IDs without apparent authorization checks.",
                                "evidence": f"{method} {url} returned {resp.status_code}",
                                "file_path": route.get("file", ""),
                                "confidence": 0.6,
                            })
                    except Exception as exc:
                        logger.debug("IDOR probe failed for %s: %s", url, exc)

        return {"findings": findings}
