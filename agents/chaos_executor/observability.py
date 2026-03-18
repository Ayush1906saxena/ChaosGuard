"""Observability — metrics collection, percentile computation, and Grafana integration.

Collects HTTP response times, error rates, and availability from health probes.
Supports optional Prometheus endpoint scraping and generates Grafana-compatible
annotation events for chaos experiment phases.
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Point-in-time snapshot of collected metrics."""

    response_times: list[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    label: str = ""  # e.g. "baseline", "during_chaos", "recovery"

    @property
    def total_requests(self) -> int:
        return self.success_count + self.error_count

    @property
    def error_rate(self) -> float:
        """Error rate as a percentage (0-100)."""
        if self.total_requests == 0:
            return 0.0
        return round((self.error_count / self.total_requests) * 100, 3)

    @property
    def availability(self) -> float:
        """Availability as a percentage (0-100)."""
        if self.total_requests == 0:
            return 0.0
        return round((self.success_count / self.total_requests) * 100, 3)

    @property
    def duration_s(self) -> float:
        if self.end_time <= 0 or self.start_time <= 0:
            return 0.0
        return round(self.end_time - self.start_time, 2)

    @property
    def p50(self) -> float:
        """Median response time in milliseconds."""
        return self._percentile(50)

    @property
    def p95(self) -> float:
        """95th percentile response time in milliseconds."""
        return self._percentile(95)

    @property
    def p99(self) -> float:
        """99th percentile response time in milliseconds."""
        return self._percentile(99)

    @property
    def mean_response_ms(self) -> float:
        if not self.response_times:
            return 0.0
        return round(statistics.mean(self.response_times), 2)

    def _percentile(self, pct: int) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * pct / 100)
        idx = min(idx, len(sorted_times) - 1)
        return round(sorted_times[idx], 2)

    def to_hypothesis_metrics(self) -> dict[str, float]:
        """Convert snapshot into the metric dict expected by HypothesisValidator."""
        return {
            "response_time_p99": self.p99,
            "response_time_p95": self.p95,
            "response_time_p50": self.p50,
            "error_rate": self.error_rate,
            "availability": self.availability,
            "mean_response_ms": self.mean_response_ms,
        }

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "availability": self.availability,
            "p50_ms": self.p50,
            "p95_ms": self.p95,
            "p99_ms": self.p99,
            "mean_response_ms": self.mean_response_ms,
            "duration_s": self.duration_s,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class SnapshotComparison:
    """Comparison between two metric snapshots (e.g. baseline vs chaos)."""

    baseline: MetricsSnapshot
    comparison: MetricsSnapshot
    label: str = ""

    @property
    def p99_change_pct(self) -> float:
        if self.baseline.p99 == 0:
            return 0.0
        return round(((self.comparison.p99 - self.baseline.p99) / self.baseline.p99) * 100, 2)

    @property
    def error_rate_change(self) -> float:
        return round(self.comparison.error_rate - self.baseline.error_rate, 3)

    @property
    def availability_change(self) -> float:
        return round(self.comparison.availability - self.baseline.availability, 3)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "baseline": self.baseline.to_dict(),
            "comparison": self.comparison.to_dict(),
            "p99_change_pct": self.p99_change_pct,
            "error_rate_change": self.error_rate_change,
            "availability_change": self.availability_change,
        }


@dataclass
class GrafanaAnnotation:
    """Grafana-compatible annotation event."""

    time_ms: int  # Unix timestamp in milliseconds
    time_end_ms: int = 0
    tags: list[str] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict:
        result: dict = {
            "time": self.time_ms,
            "tags": self.tags,
            "text": self.text,
        }
        if self.time_end_ms > 0:
            result["timeEnd"] = self.time_end_ms
        return result


class MetricsCollector:
    """Collects and aggregates metrics from health probes and optional Prometheus endpoints."""

    def __init__(self, prometheus_url: Optional[str] = None):
        self._prometheus_url = prometheus_url
        self._collecting = False
        self._current_snapshot: Optional[MetricsSnapshot] = None
        self._snapshots: list[MetricsSnapshot] = []
        self._annotations: list[GrafanaAnnotation] = []
        self._collection_task: Optional[asyncio.Task] = None

    def start_collection(self, label: str = "") -> MetricsSnapshot:
        """Begin a new collection window and return the snapshot being populated."""
        snapshot = MetricsSnapshot(
            start_time=time.time(),
            label=label,
        )
        self._current_snapshot = snapshot
        self._collecting = True
        logger.info("[metrics] Started collection: %s", label)
        return snapshot

    def stop_collection(self) -> Optional[MetricsSnapshot]:
        """Stop collecting and finalize the current snapshot."""
        self._collecting = False
        if self._current_snapshot is not None:
            self._current_snapshot.end_time = time.time()
            self._snapshots.append(self._current_snapshot)
            logger.info(
                "[metrics] Stopped collection '%s': %d requests, %.1f%% availability, p99=%.1fms",
                self._current_snapshot.label,
                self._current_snapshot.total_requests,
                self._current_snapshot.availability,
                self._current_snapshot.p99,
            )
            snapshot = self._current_snapshot
            self._current_snapshot = None
            return snapshot
        return None

    def record_probe(self, success: bool, response_time_ms: float) -> None:
        """Record a single probe result into the current collection window."""
        if not self._collecting or self._current_snapshot is None:
            return
        if success:
            self._current_snapshot.success_count += 1
        else:
            self._current_snapshot.error_count += 1
        if response_time_ms > 0:
            self._current_snapshot.response_times.append(response_time_ms)

    def snapshot(self) -> Optional[MetricsSnapshot]:
        """Return a copy of the current in-progress snapshot (non-destructive)."""
        if self._current_snapshot is None:
            return None
        snap = MetricsSnapshot(
            response_times=list(self._current_snapshot.response_times),
            error_count=self._current_snapshot.error_count,
            success_count=self._current_snapshot.success_count,
            start_time=self._current_snapshot.start_time,
            end_time=time.time(),
            label=self._current_snapshot.label + "_snapshot",
        )
        return snap

    def compare_snapshots(
        self, baseline_label: str, comparison_label: str
    ) -> Optional[SnapshotComparison]:
        """Compare two named snapshots."""
        baseline = self._find_snapshot(baseline_label)
        comparison = self._find_snapshot(comparison_label)
        if baseline is None or comparison is None:
            logger.warning(
                "[metrics] Cannot compare: baseline=%s(%s), comparison=%s(%s)",
                baseline_label, "found" if baseline else "missing",
                comparison_label, "found" if comparison else "missing",
            )
            return None
        return SnapshotComparison(
            baseline=baseline,
            comparison=comparison,
            label=f"{baseline_label}_vs_{comparison_label}",
        )

    def generate_annotation(
        self,
        text: str,
        tags: Optional[list[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> GrafanaAnnotation:
        """Create a Grafana-compatible annotation event."""
        now_ms = int(time.time() * 1000)
        annotation = GrafanaAnnotation(
            time_ms=int(start_time * 1000) if start_time else now_ms,
            time_end_ms=int(end_time * 1000) if end_time else 0,
            tags=tags or ["chaosguard"],
            text=text,
        )
        self._annotations.append(annotation)
        return annotation

    def generate_phase_annotations(self, experiment_id: str) -> list[GrafanaAnnotation]:
        """Generate annotations for all collected snapshot phases."""
        annotations = []
        for snap in self._snapshots:
            ann = self.generate_annotation(
                text=f"ChaosGuard [{snap.label}] — {snap.total_requests} reqs, "
                     f"{snap.availability}% avail, p99={snap.p99}ms",
                tags=["chaosguard", snap.label, experiment_id[:8]],
                start_time=snap.start_time if snap.start_time > 0 else None,
                end_time=snap.end_time if snap.end_time > 0 else None,
            )
            annotations.append(ann)
        return annotations

    async def scrape_prometheus(self) -> dict[str, float]:
        """Best-effort scrape of a Prometheus /metrics endpoint.

        Returns parsed metric name -> value pairs. Non-fatal on failure.
        """
        if not self._prometheus_url:
            return {}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(self._prometheus_url)
                if resp.status_code != 200:
                    return {}
                return self._parse_prometheus_text(resp.text)
        except Exception as exc:
            logger.debug("[metrics] Prometheus scrape failed (non-fatal): %s", exc)
            return {}

    def get_all_snapshots(self) -> list[dict]:
        """Return all finalized snapshots as dicts."""
        return [s.to_dict() for s in self._snapshots]

    def get_all_annotations(self) -> list[dict]:
        """Return all annotations as dicts."""
        return [a.to_dict() for a in self._annotations]

    def _find_snapshot(self, label: str) -> Optional[MetricsSnapshot]:
        for snap in self._snapshots:
            if snap.label == label:
                return snap
        return None

    @staticmethod
    def _parse_prometheus_text(text: str) -> dict[str, float]:
        """Parse Prometheus text exposition format into metric name -> value."""
        metrics: dict[str, float] = {}
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    metrics[parts[0]] = float(parts[1])
                except ValueError:
                    continue
        return metrics
