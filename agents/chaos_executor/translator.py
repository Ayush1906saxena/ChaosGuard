"""Scenario Translator — converts ChaosCascadeSimulator output into
concrete Docker-level fault injection plans."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Maps LitmusChaos experiment types to our injector fault types
LITMUS_TO_DOCKER = {
    "pod-delete": "container_kill",
    "pod-kill": "container_kill",
    "pod-network-latency": "network_delay",
    "pod-network-loss": "packet_loss",
    "pod-network-partition": "network_partition",
    "pod-cpu-hog": "cpu_stress",
    "pod-memory-hog": "memory_stress",
    "disk-fill": "disk_fill",
    "pod-network-corruption": "packet_loss",
}

# Default params for each fault type when the scenario doesn't specify
DEFAULT_PARAMS = {
    "container_kill": {"signal": "SIGKILL"},
    "container_pause": {},
    "network_delay": {"delay_ms": 500, "jitter_ms": 100},
    "network_partition": {},
    "packet_loss": {"loss_percent": 30},
    "cpu_stress": {"cores": 2, "duration_s": 30},
    "memory_stress": {"mb": 256, "duration_s": 30},
    "disk_fill": {"mb": 100},
}

# Keyword-based fault mapping for natural language scenario descriptions
KEYWORD_FAULTS = [
    (["network", "latency", "delay", "slow"], "network_delay"),
    (["partition", "split brain", "disconnect", "unreachable"], "network_partition"),
    (["packet loss", "drop", "unreliable"], "packet_loss"),
    (["kill", "crash", "stop", "terminate", "restart", "die"], "container_kill"),
    (["pause", "freeze", "hang", "unresponsive", "gc"], "container_pause"),
    (["cpu", "compute", "processing", "load"], "cpu_stress"),
    (["memory", "oom", "ram", "heap"], "memory_stress"),
    (["disk", "storage", "full", "space"], "disk_fill"),
]


@dataclass
class FaultPlan:
    fault_type: str
    target_service: str
    params: dict = field(default_factory=dict)
    delay_before_s: float = 0  # stagger for compound scenarios


@dataclass
class ExperimentPlan:
    experiment_id: str
    scenario_id: str
    scenario_title: str
    faults: list[FaultPlan] = field(default_factory=list)
    total_duration_s: int = 60
    observation_duration_s: int = 30
    description: str = ""


class ScenarioTranslator:
    """Translates chaos scenarios into Docker-level experiment plans."""

    def translate(
        self,
        scenario: dict,
        compose_services: list[str],
        experiment_id: str,
    ) -> ExperimentPlan:
        """Convert a chaos_scenario dict into an ExperimentPlan."""
        scenario_id = scenario.get("id", "unknown")
        title = scenario.get("title", "Unnamed Scenario")
        description = scenario.get("description", "")

        plan = ExperimentPlan(
            experiment_id=experiment_id,
            scenario_id=scenario_id,
            scenario_title=title,
            description=description,
        )

        # Strategy 1: Parse LitmusChaos experiment spec if present
        experiment_spec = scenario.get("experiment_spec", {})
        if experiment_spec:
            faults = self._from_litmus_spec(experiment_spec, compose_services)
            if faults:
                plan.faults = faults
                plan.total_duration_s = self._extract_duration(experiment_spec)
                plan.observation_duration_s = max(30, plan.total_duration_s // 2)
                return plan

        # Strategy 2: Parse injection_points from scenario
        injection_points = scenario.get("injection_points", [])
        if injection_points:
            faults = self._from_injection_points(injection_points, compose_services)
            if faults:
                plan.faults = faults
                return plan

        # Strategy 3: Infer faults from scenario description and affected services
        affected = self._extract_affected_services(scenario, compose_services)
        faults = self._from_description(description, title, affected)
        if faults:
            plan.faults = faults
            return plan

        # Strategy 4: Default — kill each affected service one by one
        if affected:
            for i, svc in enumerate(affected[:3]):
                plan.faults.append(FaultPlan(
                    fault_type="container_kill",
                    target_service=svc,
                    params={"signal": "SIGKILL"},
                    delay_before_s=i * 5,
                ))
            return plan

        # No mapping possible
        logger.warning("Could not translate scenario '%s' into faults", title)
        return plan

    def _from_litmus_spec(self, spec: dict, compose_services: list[str]) -> list[FaultPlan]:
        """Parse a LitmusChaos experiment spec."""
        faults = []
        experiments = spec.get("spec", {}).get("experiments", [])

        for exp in experiments:
            exp_name = exp.get("name", "")
            fault_type = LITMUS_TO_DOCKER.get(exp_name)
            if not fault_type:
                continue

            env = exp.get("spec", {}).get("components", {}).get("env", [])
            params = dict(DEFAULT_PARAMS.get(fault_type, {}))

            for e in env:
                name = e.get("name", "")
                value = e.get("value", "")
                if name == "NETWORK_LATENCY" and value:
                    params["delay_ms"] = int(value)
                elif name == "NETWORK_PACKET_LOSS_PERCENTAGE" and value:
                    params["loss_percent"] = int(value)
                elif name == "TOTAL_CHAOS_DURATION" and value:
                    params["duration_s"] = int(value)

            # Find target service — try appLabel or first available compose service
            app_label = ""
            for e in env:
                if e.get("name") == "TARGET_PODS":
                    app_label = e.get("value", "")
                    break

            target = self._match_service(app_label, compose_services)
            if target:
                faults.append(FaultPlan(
                    fault_type=fault_type,
                    target_service=target,
                    params=params,
                ))

        return faults

    def _from_injection_points(self, points: list, compose_services: list[str]) -> list[FaultPlan]:
        """Parse injection_points array from scenario."""
        faults = []
        for i, point in enumerate(points):
            if isinstance(point, str):
                # e.g. "Kill the database service"
                target = self._match_service(point, compose_services)
                fault_type = self._infer_fault_type(point)
                if target:
                    faults.append(FaultPlan(
                        fault_type=fault_type,
                        target_service=target,
                        params=dict(DEFAULT_PARAMS.get(fault_type, {})),
                        delay_before_s=i * 3,
                    ))
            elif isinstance(point, dict):
                target = self._match_service(
                    point.get("service", point.get("component", "")),
                    compose_services,
                )
                fault_type = point.get("fault_type", self._infer_fault_type(
                    point.get("description", point.get("type", ""))
                ))
                if target:
                    faults.append(FaultPlan(
                        fault_type=fault_type,
                        target_service=target,
                        params=point.get("params", dict(DEFAULT_PARAMS.get(fault_type, {}))),
                        delay_before_s=i * 3,
                    ))
        return faults

    def _from_description(self, description: str, title: str, affected: list[str]) -> list[FaultPlan]:
        """Infer faults from natural language description."""
        text = f"{title} {description}".lower()
        fault_type = self._infer_fault_type(text)
        faults = []
        for i, svc in enumerate(affected[:3]):
            faults.append(FaultPlan(
                fault_type=fault_type,
                target_service=svc,
                params=dict(DEFAULT_PARAMS.get(fault_type, {})),
                delay_before_s=i * 5,
            ))
        return faults

    def _infer_fault_type(self, text: str) -> str:
        """Infer fault type from text description."""
        text_lower = text.lower()
        for keywords, fault_type in KEYWORD_FAULTS:
            for kw in keywords:
                if kw in text_lower:
                    return fault_type
        return "container_kill"  # default

    def _match_service(self, target: str, compose_services: list[str]) -> str | None:
        """Fuzzy-match a target name to an actual compose service."""
        if not target:
            return compose_services[0] if compose_services else None

        target_lower = target.lower().strip()

        # Exact match
        for svc in compose_services:
            if svc.lower() == target_lower:
                return svc

        # Substring match
        for svc in compose_services:
            if target_lower in svc.lower() or svc.lower() in target_lower:
                return svc

        # Keyword match (e.g. "database" matches "postgres" or "db")
        db_keywords = {"database", "db", "postgres", "mysql", "mongo", "redis"}
        if any(kw in target_lower for kw in db_keywords):
            for svc in compose_services:
                if any(kw in svc.lower() for kw in db_keywords):
                    return svc

        cache_keywords = {"cache", "redis", "memcached"}
        if any(kw in target_lower for kw in cache_keywords):
            for svc in compose_services:
                if any(kw in svc.lower() for kw in cache_keywords):
                    return svc

        queue_keywords = {"queue", "kafka", "rabbitmq", "mq", "broker"}
        if any(kw in target_lower for kw in queue_keywords):
            for svc in compose_services:
                if any(kw in svc.lower() for kw in queue_keywords):
                    return svc

        return compose_services[0] if compose_services else None

    def _extract_affected_services(self, scenario: dict, compose_services: list[str]) -> list[str]:
        """Extract affected services from scenario metadata."""
        affected = []

        # Try blast_radius.directly_affected
        blast = scenario.get("blast_radius", {})
        if isinstance(blast, dict):
            for svc in blast.get("directly_affected", []):
                matched = self._match_service(str(svc), compose_services)
                if matched and matched not in affected:
                    affected.append(matched)

        # Try target_component
        target = scenario.get("target_component", "")
        if target:
            matched = self._match_service(str(target), compose_services)
            if matched and matched not in affected:
                affected.append(matched)

        # If nothing found, pick the first non-infrastructure service
        if not affected and compose_services:
            infra = {"postgres", "redis", "kafka", "zookeeper", "chromadb", "elasticsearch"}
            for svc in compose_services:
                if svc.lower() not in infra:
                    affected.append(svc)
                    break
            if not affected:
                affected.append(compose_services[0])

        return affected

    def _extract_duration(self, spec: dict) -> int:
        """Extract total duration from LitmusChaos spec."""
        for exp in spec.get("spec", {}).get("experiments", []):
            for env in exp.get("spec", {}).get("components", {}).get("env", []):
                if env.get("name") == "TOTAL_CHAOS_DURATION":
                    try:
                        return int(env.get("value", 60))
                    except (ValueError, TypeError):
                        pass
        return 60
