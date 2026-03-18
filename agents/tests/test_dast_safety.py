"""Tests for DastSafety (agents/dast/safety.py).

Covers domain allowlist, request cap, destructive payload blocking,
and rate-limiting delay enforcement.
"""

import asyncio
import time

import pytest

from dast.safety import DastSafety, MAX_REQUESTS, MIN_DELAY_MS


# ── Domain validation ────────────────────────────────────────────────


class TestDomainValidation:
    def test_allowed_domain_localhost(self):
        """localhost URLs should be allowed."""
        ds = DastSafety("http://localhost:8080/api")
        assert ds.validate_target() is True

    def test_allowed_domain_127(self):
        """127.0.0.1 URLs should be allowed."""
        ds = DastSafety("http://127.0.0.1:3000/health")
        assert ds.validate_target() is True

    def test_allowed_domain_staging(self):
        """Staging subdomain URLs should be allowed."""
        ds = DastSafety("https://app.staging.example.com/api")
        assert ds.validate_target() is True

    def test_blocked_domain_production(self):
        """Production domains without staging/dev/test patterns should be blocked."""
        ds = DastSafety("https://api.production.example.com/v1")
        assert ds.validate_target() is False

    def test_blocked_domain_plain(self):
        """Plain production domain should be blocked."""
        ds = DastSafety("https://www.example.com")
        assert ds.validate_target() is False


# ── Request cap ──────────────────────────────────────────────────────


class TestRequestCap:
    def test_request_cap_enforced(self):
        """After MAX_REQUESTS, can_make_request should return False."""
        ds = DastSafety("http://localhost:8080")
        ds.request_count = MAX_REQUESTS
        assert ds.can_make_request() is False

    def test_request_cap_not_reached(self):
        """Before reaching MAX_REQUESTS, can_make_request should return True."""
        ds = DastSafety("http://localhost:8080")
        ds.request_count = MAX_REQUESTS - 1
        assert ds.can_make_request() is True


# ── Destructive payload blocking ─────────────────────────────────────


class TestDestructivePayloads:
    @pytest.mark.parametrize(
        "payload",
        [
            "DROP TABLE users;",
            "DELETE FROM accounts WHERE 1=1",
            "TRUNCATE sessions",
            "rm -rf /",
            "; rm /etc/passwd",
            "| rm important.txt",
        ],
    )
    def test_destructive_payload_blocked(self, payload):
        """Known destructive payloads should be rejected."""
        ds = DastSafety("http://localhost:8080")
        assert ds.check_payload(payload) is False

    def test_safe_payload_allowed(self):
        """Benign payloads should be allowed through."""
        ds = DastSafety("http://localhost:8080")
        assert ds.check_payload("SELECT * FROM users WHERE id=1") is True

    def test_case_insensitive_blocking(self):
        """Destructive pattern matching should be case-insensitive."""
        ds = DastSafety("http://localhost:8080")
        assert ds.check_payload("drop table users") is False


# ── Rate limiting ────────────────────────────────────────────────────


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self):
        """Consecutive rate_limit calls should enforce MIN_DELAY_MS spacing."""
        ds = DastSafety("http://localhost:8080")

        # First call sets _last_request_time
        await ds.rate_limit()
        t1 = time.monotonic()

        # Second call should sleep to enforce the delay
        await ds.rate_limit()
        t2 = time.monotonic()

        # The gap should be at least MIN_DELAY_MS (with a small tolerance)
        elapsed_ms = (t2 - t1) * 1000
        assert elapsed_ms >= MIN_DELAY_MS * 0.8, (
            f"Rate limit gap was only {elapsed_ms:.1f}ms, expected >= {MIN_DELAY_MS}ms"
        )


# ── Request logging ──────────────────────────────────────────────────


class TestRequestLogging:
    def test_log_request_increments_count(self):
        """log_request should increment request_count and append to request_log."""
        ds = DastSafety("http://localhost:8080")
        assert ds.request_count == 0

        ds.log_request("GET", "http://localhost:8080/", 200)
        assert ds.request_count == 1
        assert len(ds.request_log) == 1
        assert ds.request_log[0]["method"] == "GET"
        assert ds.request_log[0]["status"] == 200
