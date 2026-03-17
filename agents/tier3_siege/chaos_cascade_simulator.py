import json
import logging
import os
from typing import Any

from config import config

logger = logging.getLogger(__name__)


class ChaosCascadeSimulator:
    def __init__(self):
        self.agent_name = "chaos_cascade_simulator"
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "chaos_cascade_system.txt")
        with open(prompt_path) as f:
            self.system_prompt = f.read()
        self.model = config.REASONING_MODEL

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        chaos_scenarios = state.get("chaos_scenarios", [])
        findings = state.get("findings", [])

        # Extract resilience-related findings
        resilience_findings = [
            f for f in findings
            if f.get("agent") in ("chaos_architect", "load_analyzer", "config_auditor")
            or f.get("category") in ("resilience", "performance", "configuration")
        ]

        # Combine scenarios into compound failures
        compound_scenarios = self._build_compound_failures(chaos_scenarios)

        # Calculate blast radius for each scenario using dependency info
        repo_metadata = state.get("repo_metadata", {})
        dependency_graph = repo_metadata.get("dependency_graph", {})

        scenario_summaries = []
        for i, scenario in enumerate(compound_scenarios[:10]):
            scenario_summaries.append(
                f"[S{i}] {scenario.get('title', 'Unnamed')}: "
                f"{scenario.get('description', 'No description')}"
            )

        finding_summaries = []
        for f in resilience_findings[:15]:
            finding_summaries.append(
                f"- [{f.get('severity', 'UNKNOWN')}] {f.get('title', 'Untitled')} "
                f"({f.get('file_path', 'unknown')})"
            )

        prompt = (
            f"Given these chaos engineering scenarios and resilience findings for "
            f"{state.get('repo_url', 'the target repository')}, generate comprehensive "
            f"chaos experiment specifications.\n\n"
            f"## Compound Failure Scenarios\n"
            f"{chr(10).join(scenario_summaries) if scenario_summaries else 'No pre-computed scenarios.'}\n\n"
            f"## Resilience Findings\n"
            f"{chr(10).join(finding_summaries) if finding_summaries else 'No resilience findings.'}\n\n"
            f"For each scenario:\n"
            f"1. Define the blast radius (affected services/components)\n"
            f"2. Estimate recovery time (seconds)\n"
            f"3. Generate a LitmusChaos or ChaosMesh experiment spec\n"
            f"4. Define steady-state hypothesis and abort conditions\n\n"
            f"Return JSON with 'chaos_scenarios' array."
        )

        result = await ollama_client.generate(prompt, self.system_prompt, model=self.model, expect_json=True)

        enriched_scenarios = []
        if isinstance(result, dict):
            parsed = result.get("parsed", {})
            llm_scenarios = parsed.get("chaos_scenarios", [])

            for scenario in llm_scenarios:
                scenario["agent"] = self.agent_name
                # Ensure blast radius is present
                if "blast_radius" not in scenario:
                    scenario["blast_radius"] = self._estimate_blast_radius(
                        scenario, dependency_graph
                    )
                # Ensure recovery time estimate
                if "estimated_recovery_seconds" not in scenario:
                    scenario["estimated_recovery_seconds"] = self._estimate_recovery_time(scenario)
                # Generate experiment spec if not present
                if "experiment_spec" not in scenario:
                    scenario["experiment_spec"] = self._generate_experiment_spec(scenario)
                enriched_scenarios.append(scenario)

        # Merge with original scenarios that weren't covered
        if not enriched_scenarios:
            for scenario in compound_scenarios:
                scenario["agent"] = self.agent_name
                scenario["blast_radius"] = self._estimate_blast_radius(
                    scenario, dependency_graph
                )
                scenario["estimated_recovery_seconds"] = self._estimate_recovery_time(scenario)
                scenario["experiment_spec"] = self._generate_experiment_spec(scenario)
                enriched_scenarios.append(scenario)

        return {"chaos_scenarios": enriched_scenarios}

    def _build_compound_failures(self, scenarios: list[dict]) -> list[dict]:
        """Combine individual chaos scenarios into compound failure scenarios."""
        if len(scenarios) < 2:
            return list(scenarios)

        compounds = list(scenarios)

        # Create compound scenarios by pairing related individual ones
        for i in range(len(scenarios)):
            for j in range(i + 1, min(len(scenarios), i + 5)):
                s1 = scenarios[i]
                s2 = scenarios[j]

                compound = {
                    "title": f"Compound: {s1.get('title', 'Scenario A')} + {s2.get('title', 'Scenario B')}",
                    "description": (
                        f"Simultaneous failure combining: "
                        f"({s1.get('description', 'failure 1')}) AND "
                        f"({s2.get('description', 'failure 2')})"
                    ),
                    "component_scenarios": [s1, s2],
                    "compound": True,
                    "severity": "critical" if any(
                        s.get("severity") == "critical" for s in [s1, s2]
                    ) else "high",
                }
                compounds.append(compound)

        return compounds

    def _estimate_blast_radius(self, scenario: dict, dependency_graph: dict) -> dict:
        """Estimate the blast radius of a chaos scenario."""
        affected_services = scenario.get("affected_services", [])
        affected_components = set(affected_services)

        # Walk dependency graph to find transitive dependents
        for service in affected_services:
            if service in dependency_graph:
                dependents = dependency_graph[service].get("dependents", [])
                affected_components.update(dependents)

        return {
            "directly_affected": affected_services,
            "transitively_affected": list(affected_components - set(affected_services)),
            "total_affected_count": len(affected_components),
            "severity_multiplier": 1.5 if scenario.get("compound") else 1.0,
        }

    def _estimate_recovery_time(self, scenario: dict) -> int:
        """Estimate recovery time in seconds based on scenario characteristics."""
        base_time = 30  # 30 seconds baseline

        # Compound failures take longer
        if scenario.get("compound"):
            base_time *= 3

        # More affected services = longer recovery
        blast = scenario.get("blast_radius", {})
        affected_count = blast.get("total_affected_count", 1)
        base_time += affected_count * 15

        # Critical severity adds time
        if scenario.get("severity") == "critical":
            base_time *= 2

        return min(base_time, 3600)  # Cap at 1 hour

    def _generate_experiment_spec(self, scenario: dict) -> dict:
        """Generate a LitmusChaos/ChaosMesh experiment specification."""
        title = scenario.get("title", "chaos-experiment")
        safe_name = title.lower().replace(" ", "-").replace(":", "")[:50]

        return {
            "apiVersion": "litmuschaos.io/v1alpha1",
            "kind": "ChaosEngine",
            "metadata": {
                "name": f"chaosguard-{safe_name}",
                "namespace": "litmus",
            },
            "spec": {
                "appinfo": {
                    "appns": "default",
                    "applabel": scenario.get("target_label", "app=target"),
                    "appkind": "deployment",
                },
                "engineState": "active",
                "chaosServiceAccount": "litmus-admin",
                "experiments": [
                    {
                        "name": "pod-delete",
                        "spec": {
                            "components": {
                                "env": [
                                    {"name": "TOTAL_CHAOS_DURATION", "value": "60"},
                                    {"name": "CHAOS_INTERVAL", "value": "10"},
                                    {"name": "FORCE", "value": "true"},
                                ]
                            },
                        },
                    }
                ],
                "steadyStateHypothesis": {
                    "probes": [
                        {
                            "name": "health-check",
                            "type": "httpProbe",
                            "httpProbe/inputs": {
                                "url": scenario.get("health_endpoint", "http://localhost:8080/health"),
                                "expectedResponseCode": "200",
                            },
                            "mode": "Continuous",
                            "runProperties": {"probeTimeout": 5, "interval": 5, "retry": 3},
                        }
                    ]
                },
                "abortConditions": [
                    "Error rate exceeds 90% for more than 120 seconds",
                    "Data loss detected",
                    "Unrecoverable state reached",
                ],
            },
        }
