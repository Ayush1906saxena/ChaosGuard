"""SQL injection probe agent.

Sends targeted SQL injection payloads to endpoints identified
by static analysis as potentially vulnerable.
"""
import logging

import httpx

from dast.safety import DastSafety

logger = logging.getLogger(__name__)

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "1; SELECT 1--",
    "' UNION SELECT NULL--",
    "1' AND SLEEP(2)--",
    "admin'--",
]

SQL_ERROR_INDICATORS = [
    "sql syntax",
    "mysql_fetch",
    "pg_query",
    "sqlite3.OperationalError",
    "ORA-",
    "SQLSTATE",
    "syntax error at or near",
    "unterminated quoted string",
    "microsoft ole db",
    "jdbc.sqle",
]


class SqliProbeAgent:
    def __init__(self, target_url: str, routes: list[dict]):
        self.target_url = target_url.rstrip("/")
        self.routes = routes
        self.safety = DastSafety(target_url)

    async def run(self) -> dict:
        if not self.safety.validate_target():
            return {"findings": []}

        findings = []

        # Focus on routes with parameters
        param_routes = [r for r in self.routes if r.get("params")]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for route in param_routes[:10]:
                if not self.safety.can_make_request():
                    break

                path = route["path"]
                method = route.get("method", "GET")

                for payload in SQLI_PAYLOADS:
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

                        body = resp.text.lower()
                        for indicator in SQL_ERROR_INDICATORS:
                            if indicator.lower() in body:
                                findings.append({
                                    "title": f"SQL Injection on {route['path']}",
                                    "severity": "CRITICAL",
                                    "category": "injection",
                                    "subcategory": "sql_injection",
                                    "description": f"SQL error message detected when injecting payload into {route['path']}.",
                                    "evidence": f"Payload: {payload}, Indicator: {indicator}",
                                    "file_path": route.get("file", ""),
                                    "confidence": 0.9,
                                })
                                break

                    except Exception as exc:
                        logger.debug("SQLi probe failed: %s", exc)

        return {"findings": findings}
