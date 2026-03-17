"""Shared agent scratchpad backed by Redis.

Allows agents to share intermediate findings and signals in real-time
so they can correlate discoveries across the scan.
"""
import json
import logging
from typing import Optional

import redis

from config import config

logger = logging.getLogger(__name__)

SCRATCHPAD_TTL = 7200  # 2 hours


class AgentScratchpad:
    """Per-scan scratchpad for inter-agent communication via Redis."""

    def __init__(self, scan_id: str):
        self.scan_id = scan_id
        self._redis: Optional[redis.Redis] = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(config.REDIS_URL, decode_responses=True)
        return self._redis

    def _key(self, suffix: str) -> str:
        return f"scratchpad:{self.scan_id}:{suffix}"

    def post_finding(self, agent: str, finding_summary: str) -> None:
        """Post a finding summary to the shared scratchpad."""
        try:
            r = self._get_redis()
            key = self._key("findings")
            entry = json.dumps({"agent": agent, "summary": finding_summary})
            r.rpush(key, entry)
            r.expire(key, SCRATCHPAD_TTL)
        except Exception as exc:
            logger.warning("Failed to post finding to scratchpad: %s", exc)

    def post_signal(self, agent: str, signal_text: str) -> None:
        """Post a signal (hint, warning, observation) to the shared scratchpad."""
        try:
            r = self._get_redis()
            key = self._key("signals")
            entry = json.dumps({"agent": agent, "signal": signal_text})
            r.rpush(key, entry)
            r.expire(key, SCRATCHPAD_TTL)
        except Exception as exc:
            logger.warning("Failed to post signal to scratchpad: %s", exc)

    def get_findings(self) -> list[str]:
        """Return all findings posted so far."""
        try:
            r = self._get_redis()
            raw = r.lrange(self._key("findings"), 0, -1)
            results = []
            for item in raw:
                data = json.loads(item)
                results.append(f"[{data['agent']}] {data['summary']}")
            return results
        except Exception as exc:
            logger.warning("Failed to read findings from scratchpad: %s", exc)
            return []

    def get_signals(self) -> list[str]:
        """Return all signals posted so far."""
        try:
            r = self._get_redis()
            raw = r.lrange(self._key("signals"), 0, -1)
            results = []
            for item in raw:
                data = json.loads(item)
                results.append(f"[{data['agent']}] {data['signal']}")
            return results
        except Exception as exc:
            logger.warning("Failed to read signals from scratchpad: %s", exc)
            return []

    def set_agent_status(self, agent: str, status: str) -> None:
        """Update an agent's status in the scratchpad."""
        try:
            r = self._get_redis()
            key = self._key("status")
            r.hset(key, agent, status)
            r.expire(key, SCRATCHPAD_TTL)
        except Exception as exc:
            logger.warning("Failed to set agent status in scratchpad: %s", exc)

    def get_all_statuses(self) -> dict[str, str]:
        """Get all agent statuses."""
        try:
            r = self._get_redis()
            return r.hgetall(self._key("status"))
        except Exception as exc:
            logger.warning("Failed to get agent statuses from scratchpad: %s", exc)
            return {}
