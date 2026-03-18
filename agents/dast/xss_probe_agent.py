"""Cross-Site Scripting (XSS) probe agent.

Tests reflected XSS by injecting script payloads into query parameters,
form fields, and path segments, then checking if the payload appears
unescaped in the response body.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "'onmouseover='alert(1)'",
]


class XssProbeAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Focus on routes with parameters (query params, path params)
        param_routes = [r for r in self.routes if r.get("params")]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in param_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")

                for payload in XSS_PAYLOADS:
                    if not self.safety.can_make_request():
                        break
                    if not self.safety.check_payload(payload):
                        continue

                    # Inject into path params
                    test_path = path
                    for param in route.get("params", []):
                        test_path = test_path.replace(f"{{{param}}}", payload)
                        test_path = test_path.replace(f":{param}", payload)

                    url = f"{self.target_url}{test_path}"

                    try:
                        await self.safety.rate_limit()
                        if method == "GET":
                            resp = await client.get(url)
                        else:
                            resp = await client.request(method, url, json={
                                route["params"][0]: payload if route["params"] else "test"
                            })
                        self.safety.log_request(method, url, resp.status_code, payload)

                        body = resp.text

                        # Check if payload is reflected unescaped in the response
                        if payload in body:
                            # Check for weak or missing XSS protections in headers
                            content_type = resp.headers.get("content-type", "")
                            xss_protection = resp.headers.get("x-xss-protection", "")
                            header_notes = []
                            if "text/html" in content_type:
                                header_notes.append("Content-Type is text/html")
                            if not xss_protection or xss_protection == "0":
                                header_notes.append("X-XSS-Protection is missing or disabled")

                            findings.append({
                                "title": f"Reflected XSS on {route['path']}",
                                "severity": "HIGH",
                                "category": "injection",
                                "subcategory": "xss",
                                "description": (
                                    f"XSS payload reflected unescaped in response from {route['path']}. "
                                    f"{'; '.join(header_notes) if header_notes else 'No additional header issues noted.'}"
                                ),
                                "evidence": f"Payload: {payload}, reflected in response body",
                                "file_path": route.get("file", ""),
                                "confidence": 0.8,
                            })
                            break

                    except Exception as exc:
                        logger.debug("XSS probe failed: %s", exc)

        return {"findings": findings}
