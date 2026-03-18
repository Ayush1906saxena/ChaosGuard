"""Path Traversal / Local File Inclusion (LFI) probe agent.

Tests file-related parameters by injecting directory traversal payloads
and checking if sensitive file contents are disclosed in the response.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "....//....//....//etc/passwd",
    "/etc/passwd",
    "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
]

# Parameter names likely to accept file paths
FILE_PARAM_NAMES = [
    "file", "path", "page", "template",
    "include", "dir", "document",
]

# Indicators of successful file read
FILE_CONTENT_INDICATORS = [
    "root:",          # /etc/passwd
    "[boot loader]",  # windows boot.ini
    "[fonts]",        # windows win.ini
    "daemon:",        # /etc/passwd
    "bin/bash",       # /etc/passwd shell
    "bin/sh",         # /etc/passwd shell
    "nobody:",        # /etc/passwd
]


class PathTraversalAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Filter routes with file-related parameters
        file_routes = [r for r in self.routes if any(
            any(kw in p.lower() for kw in FILE_PARAM_NAMES)
            for p in r.get("params", [])
        )]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in file_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")
                file_params = [p for p in route.get("params", [])
                               if any(kw in p.lower() for kw in FILE_PARAM_NAMES)]

                for payload in TRAVERSAL_PAYLOADS:
                    if not self.safety.can_make_request():
                        break
                    if not self.safety.check_payload(payload):
                        continue

                    # Inject payload into file-type path params
                    test_path = path
                    for param in file_params:
                        test_path = test_path.replace(f"{{{param}}}", payload)
                        test_path = test_path.replace(f":{param}", payload)

                    url = f"{self.target_url}{test_path}"

                    try:
                        await self.safety.rate_limit()
                        if method == "GET":
                            resp = await client.get(url)
                        else:
                            body = {param: payload for param in file_params}
                            resp = await client.request(method, url, json=body)
                        self.safety.log_request(method, url, resp.status_code, payload)

                        response_body = resp.text

                        for indicator in FILE_CONTENT_INDICATORS:
                            if indicator in response_body:
                                findings.append({
                                    "title": f"Path Traversal on {route['path']}",
                                    "severity": "HIGH",
                                    "category": "injection",
                                    "subcategory": "path_traversal",
                                    "description": (
                                        f"Directory traversal payload on {route['path']} "
                                        f"returned sensitive file contents."
                                    ),
                                    "evidence": f"Payload: {payload}, Indicator: {indicator}",
                                    "file_path": route.get("file", ""),
                                    "confidence": 0.85,
                                })
                                break
                        else:
                            continue
                        break  # Found a vulnerability for this route, move on

                    except Exception as exc:
                        logger.debug("Path traversal probe failed: %s", exc)

        return {"findings": findings}
