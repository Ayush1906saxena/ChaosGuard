"""CORS Misconfiguration probe agent.

Tests for overly permissive CORS policies by sending requests with
crafted Origin headers and checking if the server reflects arbitrary
origins or allows credentials with wildcards.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

MALICIOUS_ORIGINS = [
    "https://evil.com",
    "https://null",
    "https://{target}.evil.com",  # subdomain trick; {target} replaced at runtime
]


class CorsProbeAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        from urllib.parse import urlparse
        target_host = urlparse(self.target_url).hostname or "target"

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

                for origin_template in MALICIOUS_ORIGINS:
                    if not self.safety.can_make_request():
                        break

                    origin = origin_template.replace("{target}", target_host)
                    headers = {"Origin": origin}

                    try:
                        await self.safety.rate_limit()
                        resp = await client.request(method, url, headers=headers)
                        self.safety.log_request(method, url, resp.status_code, f"Origin: {origin}")

                        acao = resp.headers.get("access-control-allow-origin", "")
                        acac = resp.headers.get("access-control-allow-credentials", "").lower()

                        # Check 1: Origin reflected back exactly
                        if acao == origin:
                            description = (
                                f"Endpoint {route['path']} reflects the Origin header '{origin}' "
                                f"in Access-Control-Allow-Origin."
                            )
                            if acac == "true":
                                description += (
                                    " Combined with Access-Control-Allow-Credentials: true, "
                                    "this allows full cross-origin credential theft."
                                )

                            findings.append({
                                "title": f"CORS misconfiguration on {route['path']}",
                                "severity": "HIGH",
                                "category": "misconfiguration",
                                "subcategory": "cors",
                                "description": description,
                                "evidence": (
                                    f"Origin: {origin}, "
                                    f"ACAO: {acao}, "
                                    f"ACAC: {acac}"
                                ),
                                "file_path": route.get("file", ""),
                                "confidence": 0.95,
                            })
                            break

                        # Check 2: Wildcard with credentials
                        if acao == "*" and acac == "true":
                            findings.append({
                                "title": f"CORS wildcard with credentials on {route['path']}",
                                "severity": "HIGH",
                                "category": "misconfiguration",
                                "subcategory": "cors",
                                "description": (
                                    f"Endpoint {route['path']} returns Access-Control-Allow-Origin: * "
                                    f"with Access-Control-Allow-Credentials: true."
                                ),
                                "evidence": f"ACAO: *, ACAC: true",
                                "file_path": route.get("file", ""),
                                "confidence": 0.95,
                            })
                            break

                    except Exception as exc:
                        logger.debug("CORS probe failed: %s", exc)

        return {"findings": findings}
