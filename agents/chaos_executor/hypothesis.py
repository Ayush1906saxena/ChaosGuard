"""Steady-state hypothesis definition and validation.

Implements the core chaos engineering concept: define what 'normal' looks like
before injecting faults, then verify the system still meets those conditions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class Comparison(str, Enum):
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    EQUAL = "equal"
    BETWEEN = "between"


class HypothesisResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    DEGRADED = "degraded"  # Within tolerance but worse than baseline
    NOT_EVALUATED = "not_evaluated"


@dataclass
class SteadyStateHypothesis:
    name: str
    metric: str  # e.g. "http_response_time_p99", "error_rate", "availability"
    threshold: float
    comparison: Comparison = Comparison.LESS_THAN
    tolerance_pct: float = 10.0  # Allow N% degradation during chaos
    upper_bound: Optional[float] = None  # For BETWEEN comparison

    def evaluate(self, value: float, is_during_chaos: bool = False) -> HypothesisResult:
        """Evaluate a metric value against this hypothesis."""
        effective_threshold = self.threshold
        if is_during_chaos:
            if self.comparison == Comparison.LESS_THAN:
                effective_threshold = self.threshold * (1 + self.tolerance_pct / 100)
            elif self.comparison == Comparison.GREATER_THAN:
                effective_threshold = self.threshold * (1 - self.tolerance_pct / 100)

        passed = self._check(value, effective_threshold)
        if not passed:
            return HypothesisResult.FAILED

        if is_during_chaos and not self._check(value, self.threshold):
            return HypothesisResult.DEGRADED

        return HypothesisResult.PASSED

    def _check(self, value: float, threshold: float) -> bool:
        if self.comparison == Comparison.LESS_THAN:
            return value < threshold
        elif self.comparison == Comparison.GREATER_THAN:
            return value > threshold
        elif self.comparison == Comparison.EQUAL:
            return abs(value - threshold) < 0.001
        elif self.comparison == Comparison.BETWEEN:
            return threshold <= value <= (self.upper_bound or threshold)
        return False


@dataclass
class HypothesisEvaluation:
    hypothesis: SteadyStateHypothesis
    phase: str
    result: HypothesisResult
    measured_value: float
    threshold_used: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis.name,
            "metric": self.hypothesis.metric,
            "phase": self.phase,
            "result": self.result.value,
            "measured_value": self.measured_value,
            "threshold": self.threshold_used,
            "timestamp": self.timestamp,
        }


class HypothesisValidator:
    """Validates steady-state hypotheses across experiment phases."""

    def __init__(self, hypotheses: list[SteadyStateHypothesis]):
        self.hypotheses = hypotheses
        self.evaluations: list[HypothesisEvaluation] = []
        self.baseline_values: dict[str, float] = {}

    def record_baseline(self, metrics: dict[str, float]) -> None:
        """Record baseline metric values from the BASELINE phase."""
        self.baseline_values = dict(metrics)
        logger.info("Recorded baseline values for %d metrics", len(metrics))

    def validate(self, metrics: dict[str, float], phase: str, is_during_chaos: bool = False) -> list[HypothesisEvaluation]:
        """Validate all hypotheses against current metrics."""
        results = []
        for hyp in self.hypotheses:
            value = metrics.get(hyp.metric)
            if value is None:
                eval_result = HypothesisEvaluation(
                    hypothesis=hyp, phase=phase,
                    result=HypothesisResult.NOT_EVALUATED,
                    measured_value=0.0, threshold_used=hyp.threshold,
                )
            else:
                threshold = hyp.threshold
                if is_during_chaos and hyp.comparison == Comparison.LESS_THAN:
                    threshold = hyp.threshold * (1 + hyp.tolerance_pct / 100)

                eval_result = HypothesisEvaluation(
                    hypothesis=hyp, phase=phase,
                    result=hyp.evaluate(value, is_during_chaos),
                    measured_value=value, threshold_used=threshold,
                )

            results.append(eval_result)
            self.evaluations.append(eval_result)

            if eval_result.result == HypothesisResult.FAILED:
                logger.warning(
                    "Hypothesis FAILED: %s — measured %.3f vs threshold %.3f (phase: %s)",
                    hyp.name, eval_result.measured_value, eval_result.threshold_used, phase
                )

        return results

    def any_failed(self) -> bool:
        return any(e.result == HypothesisResult.FAILED for e in self.evaluations)

    def summary(self) -> dict:
        total = len(self.evaluations)
        passed = sum(1 for e in self.evaluations if e.result == HypothesisResult.PASSED)
        failed = sum(1 for e in self.evaluations if e.result == HypothesisResult.FAILED)
        degraded = sum(1 for e in self.evaluations if e.result == HypothesisResult.DEGRADED)
        return {
            "total_evaluations": total,
            "passed": passed,
            "failed": failed,
            "degraded": degraded,
            "all_evaluations": [e.to_dict() for e in self.evaluations],
        }


def default_hypotheses() -> list[SteadyStateHypothesis]:
    """Generate default hypotheses for common services."""
    return [
        SteadyStateHypothesis(
            name="Service responds within 500ms at p99",
            metric="response_time_p99",
            threshold=500.0,
            comparison=Comparison.LESS_THAN,
            tolerance_pct=50.0,  # Allow up to 750ms during chaos
        ),
        SteadyStateHypothesis(
            name="Error rate below 1%",
            metric="error_rate",
            threshold=1.0,
            comparison=Comparison.LESS_THAN,
            tolerance_pct=400.0,  # Allow up to 5% during chaos
        ),
        SteadyStateHypothesis(
            name="Service availability above 99%",
            metric="availability",
            threshold=99.0,
            comparison=Comparison.GREATER_THAN,
            tolerance_pct=4.0,  # Allow down to ~95% during chaos
        ),
    ]
