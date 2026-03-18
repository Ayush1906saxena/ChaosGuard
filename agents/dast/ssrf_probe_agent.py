"""Server-Side Request Forgery (SSRF) probe agent.

Tests URL-type parameters by injecting payloads targeting internal
endpoints and cloud metadata services to detect SSRF vulnerabilities.
"""
import logging
import time

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

SSRF_PAYLOADS = [
    "http://127.0.0.1:80",
    "http://localhost:8080/actuator",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]",
    "http://0x7f000001",
]

# Parameter names likely to accept URL values
URL_PARAM_NAMES = [
    "url", "link", "redirect", "callback", "dest",
    "uri", "path", "file", "fetch",
]

# Indicators that an SSRF payload reached an internal service
SSRF_INDICATORS = [
    "ami-id",
    "instance-id",
    "local-hostname",
    "meta-data",
    "iam/security-credentials",
    "actuator",
    "whitelabel error",
    "connection refused",
    "127.0.0.1",
    "localhost",
]


class SsrfProbeAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Filter routes with URL-like parameters
        url_routes = [r for r in self.routes if any(
            any(kw in p.lower() for kw in URL_PARAM_NAMES)
            for p in r.get("params", [])
        )]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in url_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")
                url_params = [p for p in route.get("params", [])
                              if any(kw in p.lower() for kw in URL_PARAM_NAMES)]

                for payload in SSRF_PAYLOADS:
                    if not self.safety.can_make_request():
                        break
                    if not self.safety.check_payload(payload):
                        continue

                    # Inject payload into URL-type path params
                    test_path = path
                    for param in url_params:
                        test_path = test_path.replace(f"{{{param}}}", payload)
                        test_path = test_path.replace(f":{param}", payload)

                    url = f"{self.target_url}{test_path}"

                    try:
                        await self.safety.rate_limit()
                        start_time = time.monotonic()

                        if method == "GET":
                            resp = await client.get(url)
                        else:
                            body = {param: payload for param in url_params}
                            resp = await client.request(method, url, json=body)

                        elapsed = time.monotonic() - start_time
                        self.safety.log_request(method, url, resp.status_code, payload)

                        response_body = resp.text.lower()

                        # Detect SSRF via response content indicators
                        detected_indicator = None
                        for indicator in SSRF_INDICATORS:
                            if indicator.lower() in response_body:
                                detected_indicator = indicator
                                break

                        # Detect SSRF via significant timing difference (> 5s may indicate internal fetch)
                        timing_suspicious = elapsed > 5.0

                        if detected_indicator or timing_suspicious:
                            evidence_parts = [f"Payload: {payload}"]
                            if detected_indicator:
                                evidence_parts.append(f"Indicator: {detected_indicator}")
                            if timing_suspicious:
                                evidence_parts.append(f"Response time: {elapsed:.2f}s")

                            findings.append({
                                "title": f"Potential SSRF on {route['path']}",
                                "severity": "CRITICAL",
                                "category": "injection",
                                "subcategory": "ssrf",
                                "description": (
                                    f"SSRF payload sent to {route['path']} produced indicators "
                                    f"of internal service access or metadata retrieval."
                                ),
                                "evidence": ", ".join(evidence_parts),
                                "file_path": route.get("file", ""),
                                "confidence": 0.7,
                            })
                            break

                    except Exception as exc:
                        logger.debug("SSRF probe failed: %s", exc)

        return {"findings": findings}
