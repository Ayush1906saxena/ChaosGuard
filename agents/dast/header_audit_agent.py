"""Security Header Audit agent.

Checks HTTP responses for the presence and correctness of security
headers such as CSP, HSTS, X-Frame-Options, and others.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

# Required security headers and their expected values / validation logic
REQUIRED_HEADERS = {
    "x-content-type-options": {
        "expected": "nosniff",
        "severity": "MEDIUM",
        "description": "Prevents MIME-type sniffing attacks.",
    },
    "x-frame-options": {
        "expected": ("DENY", "SAMEORIGIN"),
        "severity": "MEDIUM",
        "description": "Protects against clickjacking attacks.",
    },
    "strict-transport-security": {
        "expected": None,  # Just needs to be present
        "severity": "MEDIUM",
        "description": "Enforces HTTPS connections to prevent downgrade attacks.",
    },
    "content-security-policy": {
        "expected": None,
        "severity": "MEDIUM",
        "description": "Mitigates XSS and data injection attacks.",
    },
    "x-xss-protection": {
        "expected": None,
        "severity": "LOW",
        "description": "Legacy XSS filter (modern CSP is preferred).",
    },
    "referrer-policy": {
        "expected": None,
        "severity": "LOW",
        "description": "Controls how much referrer information is sent with requests.",
    },
    "permissions-policy": {
        "expected": None,
        "severity": "LOW",
        "description": "Restricts browser features like camera, microphone, geolocation.",
    },
    "cache-control": {
        "expected": None,
        "severity": "LOW",
        "description": "Controls caching behavior; sensitive endpoints should set no-store.",
    },
}


class HeaderAuditAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in self.routes[:15]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")

                # Replace path params with test values
                for param in route.get("params", []):
                    path = path.replace(f"{{{param}}}", "1")
                    path = path.replace(f":{param}", "1")

                url = f"{self.target_url}{path}"

                try:
                    await self.safety.rate_limit()
                    resp = await client.request(method, url)
                    self.safety.log_request(method, url, resp.status_code)

                    response_headers = {k.lower(): v for k, v in resp.headers.items()}

                    for header_name, config in REQUIRED_HEADERS.items():
                        value = response_headers.get(header_name)

                        if value is None:
                            # Header is missing entirely
                            findings.append({
                                "title": f"Missing {header_name} on {route['path']}",
                                "severity": config["severity"],
                                "category": "misconfiguration",
                                "subcategory": "security_headers",
                                "description": (
                                    f"Endpoint {route['path']} does not set the "
                                    f"{header_name} header. {config['description']}"
                                ),
                                "evidence": f"Header '{header_name}' not present in response",
                                "file_path": route.get("file", ""),
                                "confidence": 1.0,
                            })
                        elif config["expected"] is not None:
                            # Header present but check if value is correct
                            expected = config["expected"]
                            if isinstance(expected, tuple):
                                if value.upper() not in (e.upper() for e in expected):
                                    findings.append({
                                        "title": f"Suboptimal {header_name} on {route['path']}",
                                        "severity": "LOW",
                                        "category": "misconfiguration",
                                        "subcategory": "security_headers",
                                        "description": (
                                            f"Endpoint {route['path']} sets {header_name} "
                                            f"to '{value}', expected one of {expected}."
                                        ),
                                        "evidence": f"{header_name}: {value}",
                                        "file_path": route.get("file", ""),
                                        "confidence": 1.0,
                                    })
                            elif isinstance(expected, str):
                                if value.lower() != expected.lower():
                                    findings.append({
                                        "title": f"Suboptimal {header_name} on {route['path']}",
                                        "severity": "LOW",
                                        "category": "misconfiguration",
                                        "subcategory": "security_headers",
                                        "description": (
                                            f"Endpoint {route['path']} sets {header_name} "
                                            f"to '{value}', expected '{expected}'."
                                        ),
                                        "evidence": f"{header_name}: {value}",
                                        "file_path": route.get("file", ""),
                                        "confidence": 1.0,
                                    })

                except Exception as exc:
                    logger.debug("Header audit failed for %s: %s", url, exc)

        return {"findings": findings}
