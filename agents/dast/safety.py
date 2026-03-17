"""DAST safety controls.

Rate limiter, request cap, domain allowlist, destructive payload blocker,
and request logger to prevent DAST probes from causing harm.
"""
import asyncio
import logging
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Allowed domain patterns (staging, dev, test, localhost)
ALLOWED_DOMAIN_PATTERNS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    ".staging.",
    ".dev.",
    ".test.",
    "-staging.",
    "-dev.",
    "-test.",
    "staging-",
    "dev-",
    "test-",
    ".local",
    ".internal",
]

# Maximum requests per DAST scan
MAX_REQUESTS = 500

# Minimum delay between requests (ms)
MIN_DELAY_MS = 100

# Destructive HTTP methods/payloads to block
DESTRUCTIVE_PATTERNS = [
    "DROP TABLE",
    "DELETE FROM",
    "TRUNCATE",
    "rm -rf",
    "shutdown",
    "format c:",
    "; rm ",
    "| rm ",
]


class DastSafety:
    """Safety controls for DAST probing."""

    def __init__(self, target_url: str):
        self.target_url = target_url
        self.request_count = 0
        self.request_log: list[dict] = []
        self._last_request_time = 0.0

    def validate_target(self) -> bool:
        """Check if target URL is in the allowed domain list."""
        parsed = urlparse(self.target_url)
        hostname = parsed.hostname or ""

        for pattern in ALLOWED_DOMAIN_PATTERNS:
            if pattern in hostname:
                return True

        logger.error(
            "Target URL %s is NOT in allowed domain list. "
            "DAST probes are only allowed against staging/dev/test/localhost.",
            self.target_url,
        )
        return False

    def can_make_request(self) -> bool:
        """Check if we can make another request."""
        if self.request_count >= MAX_REQUESTS:
            logger.warning("DAST request cap reached (%d)", MAX_REQUESTS)
            return False
        return True

    async def rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        now = time.monotonic()
        elapsed_ms = (now - self._last_request_time) * 1000
        if elapsed_ms < MIN_DELAY_MS:
            await asyncio.sleep((MIN_DELAY_MS - elapsed_ms) / 1000)
        self._last_request_time = time.monotonic()

    def check_payload(self, payload: str) -> bool:
        """Block destructive payloads."""
        payload_upper = payload.upper()
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.upper() in payload_upper:
                logger.warning("Blocked destructive payload: %s", pattern)
                return False
        return True

    def log_request(self, method: str, url: str, status: int, payload: str = "") -> None:
        """Log a DAST request."""
        self.request_count += 1
        entry = {
            "request_num": self.request_count,
            "method": method,
            "url": url,
            "status": status,
            "payload_preview": payload[:100] if payload else "",
            "timestamp": time.time(),
        }
        self.request_log.append(entry)
        logger.debug("DAST request #%d: %s %s -> %d", self.request_count, method, url, status)
