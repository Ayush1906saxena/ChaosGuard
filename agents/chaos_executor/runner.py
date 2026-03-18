"""Experiment Runner — full lifecycle execution of a chaos experiment.

Phases: Plan → Provision → Baseline → Approve → Inject → Observe → Rollback → Recovery → Teardown → Report
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

import psycopg2

from config import config
from chaos_executor.hypothesis import HypothesisValidator, HypothesisResult, default_hypotheses
from chaos_executor.injectors import INJECTOR_REGISTRY, InjectionResult
from chaos_executor.observability import MetricsCollector
from chaos_executor.probes import HealthProber, ProbeResult, ProbeTarget
from chaos_executor.safety import SafetyController, SafetyLimits
from chaos_executor.sandbox import SandboxOrchestrator, SandboxState
from chaos_executor.translator import ExperimentPlan, ScenarioTranslator

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    experiment_id: str
    scan_id: str
    scenario_id: str
    status: str  # COMPLETED, FAILED, ABORTED, ERROR
    phase: str = "PENDING"
    resilience_score: float = 0.0
    baseline_metrics: dict = field(default_factory=dict)
    chaos_metrics: dict = field(default_factory=dict)
    recovery_metrics: dict = field(default_factory=dict)
    recovery_time_s: float = 0.0
    faults_injected: list[dict] = field(default_factory=list)
    health_timeline: list[dict] = field(default_factory=list)
    verdict: str = ""
    recommendations: list[str] = field(default_factory=list)
    hypothesis_summary: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    error: str = ""


class ExperimentRunner:
    """Orchestrates the full chaos experiment lifecycle."""

    def __init__(self):
        self.sandbox = SandboxOrchestrator()
        self.translator = ScenarioTranslator()
        self.prober = HealthProber()
        self.safety = SafetyController()
        self._active_injections: list[InjectionResult] = []
        self._sandbox_state: SandboxState | None = None
        self._hypothesis_validator: HypothesisValidator | None = None
        self._metrics_collector: MetricsCollector | None = None

    async def run_experiment(
        self,
        scan_id: str,
        scenario: dict,
        clone_path: str,
        auto_approve: bool = False,
    ) -> ExperimentResult:
        """Execute a complete chaos experiment."""
        experiment_id = str(uuid.uuid4())
        result = ExperimentResult(
            experiment_id=experiment_id,
            scan_id=scan_id,
            scenario_id=scenario.get("id", ""),
            status="RUNNING",
            started_at=datetime.utcnow().isoformat(),
        )

        if auto_approve:
            self.safety.limits.require_approval = False

        if not self.safety.set_active_experiment(scan_id, experiment_id):
            result.status = "ERROR"
            result.error = "Another experiment is already running for this scan"
            return result

        try:
            # === Phase 1: Plan ===
            result.phase = "PLANNING"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: PLANNING experiment %s", experiment_id[:8])

            compose_file = self.sandbox.find_compose_file(clone_path)
            if not compose_file:
                result.status = "ERROR"
                result.error = "No docker-compose.yml found in repository"
                return result

            import yaml
            with open(compose_file) as f:
                compose_data = yaml.safe_load(f)
            compose_services = list(compose_data.get("services", {}).keys())

            plan = self.translator.translate(scenario, compose_services, experiment_id)
            if not plan.faults:
                result.status = "ERROR"
                result.error = "Could not translate scenario into executable faults"
                return result

            # Validate plan
            plan_dict = {
                "faults": [{"target_service": f.target_service, "fault_type": f.fault_type, "params": f.params} for f in plan.faults],
                "total_duration_s": plan.total_duration_s,
            }
            errors = self.safety.validate_experiment(plan_dict)
            if errors:
                result.status = "ERROR"
                result.error = "; ".join(errors)
                return result

            # === Phase 2: Provision ===
            result.phase = "PROVISIONING"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: PROVISIONING sandbox for %s", experiment_id[:8])

            self._sandbox_state = await self.sandbox.provision(scan_id, clone_path)
            ready = await self.sandbox.wait_ready(self._sandbox_state, timeout_s=120)
            if not ready:
                result.status = "ERROR"
                result.error = "Sandbox containers failed to start within timeout"
                return result

            # === Phase 3: Baseline ===
            result.phase = "BASELINE"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: BASELINE collection for %s", experiment_id[:8])

            exposed_ports = await self.sandbox.get_exposed_ports(self._sandbox_state)
            probe_targets = await self.prober.discover_endpoints(clone_path, exposed_ports)

            baseline_probes = await self.prober.probe_continuously(
                probe_targets, duration_s=15, interval_s=2
            )
            result.baseline_metrics = self._compute_metrics(baseline_probes)
            result.health_timeline.extend([asdict(p) for p in baseline_probes])

            # Initialize hypothesis validator and record baseline
            self._hypothesis_validator = HypothesisValidator(default_hypotheses())
            baseline_hyp_metrics = self._to_hypothesis_metrics(result.baseline_metrics)
            self._hypothesis_validator.record_baseline(baseline_hyp_metrics)

            # === Phase 4: Approval ===
            result.phase = "PENDING_APPROVAL"
            self._persist_experiment(result, plan_dict=plan_dict)
            logger.info("[chaos] Phase: PENDING_APPROVAL for %s", experiment_id[:8])

            approved = await self.safety.request_approval(experiment_id)
            if not approved:
                result.status = "REJECTED"
                result.phase = "REJECTED"
                return result

            # === Phase 5: Steady-state check ===
            result.phase = "STEADY_STATE"
            self._persist_experiment(result)

            steady_probes = await self.prober.probe_once(probe_targets)
            steady_ok = any(p.success for p in steady_probes)
            if not steady_ok:
                logger.warning("[chaos] Steady-state check failed, proceeding anyway")

            # Validate hypotheses at steady-state (pre-chaos)
            if self._hypothesis_validator:
                steady_metrics = self._compute_metrics(steady_probes)
                steady_hyp_metrics = self._to_hypothesis_metrics(steady_metrics)
                self._hypothesis_validator.validate(
                    steady_hyp_metrics, phase="STEADY_STATE", is_during_chaos=False
                )

            # === Phase 6: Injection ===
            result.phase = "INJECTING"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: INJECTING faults for %s", experiment_id[:8])

            for fault_plan in plan.faults:
                if self.safety.is_aborted(scan_id):
                    result.status = "ABORTED"
                    break

                if fault_plan.delay_before_s > 0:
                    await asyncio.sleep(fault_plan.delay_before_s)

                container_id = self._sandbox_state.container_ids.get(fault_plan.target_service)
                if not container_id:
                    logger.warning("[chaos] Service '%s' not found in sandbox, skipping", fault_plan.target_service)
                    continue

                injector = INJECTOR_REGISTRY.get(fault_plan.fault_type)
                if not injector:
                    logger.warning("[chaos] Unknown fault type '%s', skipping", fault_plan.fault_type)
                    continue

                # For network partition, resolve target IP
                if fault_plan.fault_type == "network_partition" and "target_ip" not in fault_plan.params:
                    # Partition from the first other service
                    for other_svc, other_cid in self._sandbox_state.container_ids.items():
                        if other_svc != fault_plan.target_service:
                            ip = await self.sandbox.get_service_ip(self._sandbox_state, other_svc)
                            if ip:
                                fault_plan.params["target_ip"] = ip
                                break

                injection = await injector.inject(container_id, fault_plan.target_service, fault_plan.params)
                self._active_injections.append(injection)
                result.faults_injected.append(asdict(injection))
                self._persist_experiment(result)

            if result.status == "ABORTED":
                return result

            # === Phase 7: Observation ===
            result.phase = "OBSERVING"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: OBSERVING for %ds", plan.observation_duration_s)

            chaos_probes = await self._observe_with_abort_check(
                probe_targets, plan.observation_duration_s, scan_id
            )
            result.chaos_metrics = self._compute_metrics(chaos_probes)
            result.health_timeline.extend([asdict(p) for p in chaos_probes])

            # Validate hypotheses during chaos — trigger early abort on failure
            if self._hypothesis_validator:
                chaos_hyp_metrics = self._to_hypothesis_metrics(result.chaos_metrics)
                chaos_evals = self._hypothesis_validator.validate(
                    chaos_hyp_metrics, phase="OBSERVING", is_during_chaos=True
                )
                failed_during_chaos = [
                    e for e in chaos_evals if e.result == HypothesisResult.FAILED
                ]
                if failed_during_chaos:
                    logger.warning(
                        "[chaos] %d hypothesis(es) FAILED during chaos — triggering early abort",
                        len(failed_during_chaos),
                    )
                    result.status = "ABORTED"

            if self.safety.is_aborted(scan_id):
                result.status = "ABORTED"

            # === Phase 8: Rollback ===
            result.phase = "ROLLING_BACK"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: ROLLING_BACK for %s", experiment_id[:8])

            await self._rollback_all()

            # === Phase 9: Recovery ===
            result.phase = "RECOVERING"
            self._persist_experiment(result)
            logger.info("[chaos] Phase: RECOVERING for %s", experiment_id[:8])

            recovery_start = time.time()
            recovery_probes = await self.prober.probe_continuously(
                probe_targets, duration_s=30, interval_s=2
            )
            result.recovery_metrics = self._compute_metrics(recovery_probes)
            result.health_timeline.extend([asdict(p) for p in recovery_probes])

            # Calculate recovery time (first successful probe after rollback)
            for p in recovery_probes:
                if p.success:
                    result.recovery_time_s = round(time.time() - recovery_start, 1)
                    break
            else:
                result.recovery_time_s = 30.0  # didn't recover

            # Validate hypotheses post-recovery (should return to steady-state)
            if self._hypothesis_validator:
                recovery_hyp_metrics = self._to_hypothesis_metrics(result.recovery_metrics)
                self._hypothesis_validator.validate(
                    recovery_hyp_metrics, phase="RECOVERING", is_during_chaos=False
                )

            # === Phase 10: Score ===
            result.resilience_score = self._compute_resilience_score(result)
            result.verdict = self._generate_verdict(result)
            result.recommendations = self._generate_recommendations(result)

            # Include hypothesis summary in experiment result
            if self._hypothesis_validator:
                result.hypothesis_summary = self._hypothesis_validator.summary()

            if result.status not in ("ABORTED", "REJECTED"):
                result.status = "COMPLETED"

            result.phase = "COMPLETED"
            logger.info("[chaos] Experiment %s completed: score=%.0f, verdict=%s",
                        experiment_id[:8], result.resilience_score, result.verdict[:50])

        except Exception as exc:
            result.status = "ERROR"
            result.error = str(exc)
            logger.error("[chaos] Experiment %s failed: %s", experiment_id[:8], exc)
            # Emergency rollback
            await self._rollback_all()

        finally:
            result.completed_at = datetime.utcnow().isoformat()
            self._persist_experiment(result)
            self.safety.clear_active_experiment(scan_id)
            self.safety.clear_emergency_stop(scan_id)

            # Teardown sandbox
            if self._sandbox_state and self._sandbox_state.is_running:
                try:
                    await self.sandbox.teardown(self._sandbox_state)
                except Exception as exc:
                    logger.error("[chaos] Sandbox teardown error: %s", exc)

            self._sandbox_state = None
            self._active_injections = []
            self._hypothesis_validator = None
            self._metrics_collector = None

        return result

    # ── Internal helpers ──────────────────────────────────────────────

    async def _observe_with_abort_check(
        self, targets: list[ProbeTarget], duration_s: float, scan_id: str
    ) -> list[ProbeResult]:
        """Probe continuously but check for abort signal."""
        results: list[ProbeResult] = []
        deadline = time.time() + duration_s
        interval = 2.0

        async with __import__("httpx").AsyncClient(timeout=__import__("httpx").Timeout(5.0)) as client:
            while time.time() < deadline:
                if self.safety.is_aborted(scan_id):
                    break
                batch = await self.prober.probe_once(targets)
                results.extend(batch)
                await asyncio.sleep(interval)

        return results

    async def _rollback_all(self) -> None:
        """Rollback all active injections in LIFO order."""
        for injection in reversed(self._active_injections):
            if injection.success:
                injector = INJECTOR_REGISTRY.get(injection.fault_type)
                if injector:
                    try:
                        await injector.rollback(injection)
                    except Exception as exc:
                        logger.error("[rollback] Failed for %s: %s", injection.injection_id, exc)
        self._active_injections = []

    @staticmethod
    def _to_hypothesis_metrics(computed_metrics: dict) -> dict[str, float]:
        """Convert computed probe metrics into the format expected by HypothesisValidator.

        Maps runner metric keys to hypothesis metric names:
          - p99_response_ms  -> response_time_p99
          - success_rate     -> availability (and inverse for error_rate)
        """
        success_rate = computed_metrics.get("success_rate", 0)
        return {
            "response_time_p99": computed_metrics.get("p99_response_ms", 0),
            "error_rate": max(0, 100.0 - success_rate),
            "availability": success_rate,
        }

    def _compute_metrics(self, probes: list[ProbeResult]) -> dict:
        """Compute aggregate metrics from probe results."""
        if not probes:
            return {"total": 0, "success_rate": 0, "avg_response_ms": 0, "p99_response_ms": 0}

        total = len(probes)
        successes = sum(1 for p in probes if p.success)
        times = [p.response_time_ms for p in probes if p.response_time_ms > 0]

        return {
            "total": total,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
            "avg_response_ms": round(sum(times) / len(times), 1) if times else 0,
            "p99_response_ms": round(sorted(times)[int(len(times) * 0.99)] if times else 0, 1),
            "error_count": total - successes,
        }

    def _compute_resilience_score(self, result: ExperimentResult) -> float:
        """Compute 0-100 resilience score."""
        score = 0.0

        # Availability during chaos (40% weight)
        chaos_rate = result.chaos_metrics.get("success_rate", 0)
        score += (chaos_rate / 100) * 40

        # Recovery time (30% weight) — under 10s = full marks, 30s+ = 0
        recovery = result.recovery_time_s
        if recovery <= 5:
            score += 30
        elif recovery <= 10:
            score += 25
        elif recovery <= 20:
            score += 15
        elif recovery <= 30:
            score += 5

        # Graceful degradation (20% weight) — compare baseline vs chaos
        baseline_rate = result.baseline_metrics.get("success_rate", 100)
        if baseline_rate > 0:
            degradation_ratio = chaos_rate / baseline_rate
            score += degradation_ratio * 20

        # Recovery completeness (10% weight)
        recovery_rate = result.recovery_metrics.get("success_rate", 0)
        score += (recovery_rate / 100) * 10

        return round(min(100, max(0, score)), 1)

    def _generate_verdict(self, result: ExperimentResult) -> str:
        """Human-readable verdict."""
        score = result.resilience_score
        chaos_rate = result.chaos_metrics.get("success_rate", 0)
        recovery = result.recovery_time_s

        if score >= 80:
            return f"RESILIENT — Application maintained {chaos_rate}% availability during chaos and recovered in {recovery}s."
        elif score >= 60:
            return f"PARTIALLY RESILIENT — {chaos_rate}% availability during fault injection. Recovery took {recovery}s. Some degradation observed."
        elif score >= 40:
            return f"DEGRADED — Significant availability impact ({chaos_rate}%). Recovery took {recovery}s. Resilience improvements needed."
        else:
            return f"FRAGILE — Application severely impacted ({chaos_rate}% availability). Recovery: {recovery}s. Critical resilience gaps found."

    def _generate_recommendations(self, result: ExperimentResult) -> list[str]:
        """Generate actionable recommendations."""
        recs = []
        chaos_rate = result.chaos_metrics.get("success_rate", 0)
        recovery = result.recovery_time_s
        baseline_avg = result.baseline_metrics.get("avg_response_ms", 0)
        chaos_avg = result.chaos_metrics.get("avg_response_ms", 0)

        if chaos_rate < 50:
            recs.append("Add circuit breakers to prevent cascade failures when dependencies are unavailable.")
        if chaos_rate < 80:
            recs.append("Implement retry logic with exponential backoff for failed service calls.")
        if recovery > 15:
            recs.append("Add health checks and automatic restart policies to reduce recovery time.")
        if recovery > 30:
            recs.append("Implement a readiness probe so load balancers stop routing to unhealthy instances.")
        if chaos_avg > baseline_avg * 3 and baseline_avg > 0:
            recs.append("Add request timeouts to prevent slow cascading failures.")
        if len(result.faults_injected) > 1 and chaos_rate < 60:
            recs.append("Consider implementing bulkhead isolation to contain failures to individual services.")

        for fault in result.faults_injected:
            ft = fault.get("fault_type", "")
            if ft == "network_partition" and chaos_rate < 70:
                recs.append("Implement graceful degradation for network partition scenarios (e.g., local caching, queue-based retry).")
            elif ft == "container_kill" and recovery > 10:
                recs.append("Configure container restart policies (e.g., restart: unless-stopped) for faster recovery from crashes.")

        return recs[:6]

    def _persist_experiment(self, result: ExperimentResult, plan_dict: dict | None = None) -> None:
        """Persist experiment state to PostgreSQL."""
        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chaos_experiments
                            (id, scan_id, scenario_id, status, experiment_plan,
                             baseline_metrics, chaos_metrics, recovery_metrics,
                             resilience_score, recovery_time_s, faults_injected,
                             health_timeline, verdict, recommendations,
                             started_at, completed_at)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            status = EXCLUDED.status,
                            experiment_plan = COALESCE(EXCLUDED.experiment_plan, chaos_experiments.experiment_plan),
                            baseline_metrics = EXCLUDED.baseline_metrics,
                            chaos_metrics = EXCLUDED.chaos_metrics,
                            recovery_metrics = EXCLUDED.recovery_metrics,
                            resilience_score = EXCLUDED.resilience_score,
                            recovery_time_s = EXCLUDED.recovery_time_s,
                            faults_injected = EXCLUDED.faults_injected,
                            health_timeline = EXCLUDED.health_timeline,
                            verdict = EXCLUDED.verdict,
                            recommendations = EXCLUDED.recommendations,
                            completed_at = EXCLUDED.completed_at
                        """,
                        (
                            result.experiment_id,
                            result.scan_id,
                            result.scenario_id,
                            result.status,
                            json.dumps(plan_dict) if plan_dict else json.dumps({}),
                            json.dumps(result.baseline_metrics),
                            json.dumps(result.chaos_metrics),
                            json.dumps(result.recovery_metrics),
                            result.resilience_score,
                            result.recovery_time_s,
                            json.dumps(result.faults_injected),
                            json.dumps(result.health_timeline[-100:]),  # limit timeline size
                            result.verdict,
                            json.dumps(result.recommendations),
                            result.started_at or None,
                            result.completed_at or None,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[chaos] Failed to persist experiment: %s", exc)
