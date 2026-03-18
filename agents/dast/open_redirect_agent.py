"""Open Redirect probe agent.

Tests redirect-related parameters by injecting external URLs and checking
if the server issues a 3xx redirect to an attacker-controlled domain.
"""
import logging
from urllib.parse import urlparse

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

REDIRECT_PAYLOADS = [
    "https://evil.com",
    "//evil.com",
    "/\\evil.com",
    "https://evil.com%00.legitimate.com",
    "javascript:alert(1)",
]

# Parameter names likely to accept redirect destinations
REDIRECT_PARAM_NAMES = [
    "redirect", "url", "next", "return",
    "goto", "dest", "continue", "redir",
]


class OpenRedirectAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Filter routes with redirect-like parameters
        redirect_routes = [r for r in self.routes if any(
            any(kw in p.lower() for kw in REDIRECT_PARAM_NAMES)
            for p in r.get("params", [])
        )]

        target_host = urlparse(self.target_url).hostname or ""

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            for route in redirect_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")
                redir_params = [p for p in route.get("params", [])
                                if any(kw in p.lower() for kw in REDIRECT_PARAM_NAMES)]

                for payload in REDIRECT_PAYLOADS:
                    if not self.safety.can_make_request():
                        break
                    if not self.safety.check_payload(payload):
                        continue

                    # Inject payload into redirect-type path params
                    test_path = path
                    for param in redir_params:
                        test_path = test_path.replace(f"{{{param}}}", payload)
                        test_path = test_path.replace(f":{param}", payload)

                    url = f"{self.target_url}{test_path}"

                    try:
                        await self.safety.rate_limit()
                        if method == "GET":
                            resp = await client.get(url)
                        else:
                            body = {param: payload for param in redir_params}
                            resp = await client.request(method, url, json=body)
                        self.safety.log_request(method, url, resp.status_code, payload)

                        # Check for 3xx redirect to external domain
                        if 300 <= resp.status_code < 400:
                            location = resp.headers.get("location", "")
                            location_host = urlparse(location).hostname or ""

                            # Redirect points to an external domain
                            if location_host and location_host != target_host:
                                findings.append({
                                    "title": f"Open Redirect on {route['path']}",
                                    "severity": "MEDIUM",
                                    "category": "redirect",
                                    "subcategory": "open_redirect",
                                    "description": (
                                        f"Endpoint {route['path']} redirects to external domain "
                                        f"'{location_host}' when given a crafted redirect parameter."
                                    ),
                                    "evidence": (
                                        f"Payload: {payload}, "
                                        f"Status: {resp.status_code}, "
                                        f"Location: {location}"
                                    ),
                                    "file_path": route.get("file", ""),
                                    "confidence": 0.9,
                                })
                                break

                    except Exception as exc:
                        logger.debug("Open redirect probe failed: %s", exc)

        return {"findings": findings}
