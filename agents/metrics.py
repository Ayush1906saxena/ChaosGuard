"""Scan metrics tracking via Redis with flush to PostgreSQL.

Records timing, finding counts, and LLM latency per scan phase.
"""
import json
import logging
import time
from typing import Optional

import redis

from config import config

logger = logging.getLogger(__name__)


class ScanMetrics:
    """Tracks scan-level metrics using Redis hashes, flushed to PostgreSQL at end."""

    def __init__(self, scan_id: str):
        self.scan_id = scan_id
        self._redis: Optional[redis.Redis] = None
        self._key = f"metrics:{scan_id}"
        self._phase_starts: dict[str, float] = {}

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(config.REDIS_URL, decode_responses=True)
        return self._redis

    def record_phase_start(self, phase: str) -> None:
        """Record the start time of a phase."""
        self._phase_starts[phase] = time.monotonic()
        try:
            r = self._get_redis()
            r.hset(self._key, f"{phase}_start", str(time.time()))
            r.expire(self._key, 7200)
        except Exception:
            pass

    def record_phase_end(self, phase: str) -> None:
        """Record the end time of a phase and compute duration."""
        start = self._phase_starts.get(phase)
        if start is not None:
            duration = time.monotonic() - start
            try:
                r = self._get_redis()
                r.hset(self._key, f"{phase}_duration_s", str(round(duration, 2)))
            except Exception:
                pass

    def record_llm_call(self, duration_s: float) -> None:
        """Record an LLM call's latency."""
        try:
            r = self._get_redis()
            r.hincrby(self._key, "llm_call_count", 1)
            r.hincrbyfloat(self._key, "llm_total_latency_s", round(duration_s, 3))
        except Exception:
            pass

    def record_finding_counts(self, findings: list[dict]) -> None:
        """Record finding counts by severity."""
        counts: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "unknown").lower()
            counts[sev] = counts.get(sev, 0) + 1
        try:
            r = self._get_redis()
            r.hset(self._key, "finding_counts", json.dumps(counts))
        except Exception:
            pass

    def flush_to_db(self, scan_id: str, tier: str) -> None:
        """Write accumulated metrics from Redis to PostgreSQL scan_metrics table."""
        try:
            r = self._get_redis()
            data = r.hgetall(self._key)
            if not data:
                return

            import psycopg2
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO scan_metrics (
                            scan_id, tier,
                            total_duration_s, recon_duration_s,
                            hunter_duration_s, siege_duration_s,
                            finding_counts, llm_call_count, llm_total_latency_s
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            scan_id,
                            tier.upper(),
                            float(data.get("total_duration_s", 0)),
                            float(data.get("recon_duration_s", 0)),
                            float(data.get("hunter_duration_s", 0)),
                            float(data.get("siege_duration_s", 0)),
                            data.get("finding_counts", "{}"),
                            int(data.get("llm_call_count", 0)),
                            float(data.get("llm_total_latency_s", 0)),
                        ),
                    )
                conn.commit()
                logger.info("Flushed metrics to DB for scan %s", scan_id)
            finally:
                conn.close()

            # Clean up Redis key
            r.delete(self._key)

        except Exception as exc:
            logger.warning("Failed to flush metrics to DB: %s", exc)
