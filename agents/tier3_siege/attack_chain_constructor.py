import logging
import os
from typing import Any

from config import config

logger = logging.getLogger(__name__)

# MITRE ATT&CK mapping for common vulnerability categories
MITRE_MAPPING = {
    "injection": {"tactic": "Execution", "technique": "T1059", "name": "Command and Scripting Interpreter"},
    "secret": {"tactic": "Credential Access", "technique": "T1552", "name": "Unsecured Credentials"},
    "authentication": {"tactic": "Initial Access", "technique": "T1078", "name": "Valid Accounts"},
    "authorization": {"tactic": "Privilege Escalation", "technique": "T1068", "name": "Exploitation for Privilege Escalation"},
    "configuration": {"tactic": "Defense Evasion", "technique": "T1562", "name": "Impair Defenses"},
    "dependency": {"tactic": "Initial Access", "technique": "T1195", "name": "Supply Chain Compromise"},
    "code_execution": {"tactic": "Execution", "technique": "T1203", "name": "Exploitation for Client Execution"},
    "cryptography": {"tactic": "Credential Access", "technique": "T1110", "name": "Brute Force"},
    "input_validation": {"tactic": "Initial Access", "technique": "T1190", "name": "Exploit Public-Facing Application"},
    "ssrf": {"tactic": "Lateral Movement", "technique": "T1210", "name": "Exploitation of Remote Services"},
    "deserialization": {"tactic": "Execution", "technique": "T1059", "name": "Command and Scripting Interpreter"},
    "path_traversal": {"tactic": "Collection", "technique": "T1005", "name": "Data from Local System"},
    "xss": {"tactic": "Initial Access", "technique": "T1189", "name": "Drive-by Compromise"},
}


class AttackChainConstructor:
    def __init__(self):
        self.agent_name = "attack_chain_constructor"
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "attack_chain_system.txt")
        with open(prompt_path) as f:
            self.system_prompt = f.read()
        self.model = config.REASONING_MODEL

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        findings = state.get("findings", [])
        if not findings:
            return {"attack_chains": []}

        # Build finding graph with 'enables' relationships
        finding_graph = self._build_finding_graph(findings)

        # Prepare finding summaries for LLM
        finding_summaries = []
        for i, f in enumerate(findings[:30]):
            mitre = MITRE_MAPPING.get(f.get("category", ""), {})
            finding_summaries.append(
                f"[F{i}] {f.get('severity', 'UNKNOWN')} | {f.get('category', 'unknown')} | "
                f"{f.get('title', 'Untitled')} | File: {f.get('file_path', 'unknown')} | "
                f"MITRE: {mitre.get('technique', 'N/A')} {mitre.get('name', 'N/A')}"
            )

        # Format graph edges
        edge_descriptions = []
        for src_idx, targets in finding_graph.items():
            for tgt_idx, relationship in targets:
                edge_descriptions.append(f"F{src_idx} --[{relationship}]--> F{tgt_idx}")

        prompt = (
            f"Given the following security findings from a scan of {state.get('repo_url', '')}, "
            f"construct multi-step attack chains that show how an attacker could combine "
            f"multiple vulnerabilities to achieve high-impact objectives.\n\n"
            f"## Findings\n"
            f"{chr(10).join(finding_summaries)}\n\n"
            f"## Known Relationships\n"
            f"{chr(10).join(edge_descriptions) if edge_descriptions else 'No pre-computed relationships.'}\n\n"
            f"For each attack chain, provide:\n"
            f"1. A narrative title\n"
            f"2. The ordered sequence of findings (by F-index) that form the chain\n"
            f"3. The overall impact and blast radius\n"
            f"4. MITRE ATT&CK tactic/technique mapping for each step\n"
            f"5. Likelihood rating (HIGH/MEDIUM/LOW)\n\n"
            f"Return JSON with a 'attack_chains' array."
        )

        result = await ollama_client.generate(prompt, self.system_prompt, model=self.model, expect_json=True)
        attack_chains = []
        if isinstance(result, dict):
            parsed = result.get("parsed", {})
            raw_chains = parsed.get("attack_chains", [])

            for chain in raw_chains:
                # Enrich with MITRE mappings
                steps = chain.get("steps", chain.get("findings", []))
                enriched_steps = []
                for step in steps:
                    finding_idx = step.get("finding_index", step.get("index", -1))
                    if 0 <= finding_idx < len(findings):
                        f = findings[finding_idx]
                        cat = f.get("category", "")
                        mitre = MITRE_MAPPING.get(cat, {})
                        step["mitre_tactic"] = step.get("mitre_tactic", mitre.get("tactic", "Unknown"))
                        step["mitre_technique"] = step.get("mitre_technique", mitre.get("technique", "Unknown"))
                        step["mitre_name"] = step.get("mitre_name", mitre.get("name", "Unknown"))
                    enriched_steps.append(step)
                chain["steps"] = enriched_steps
                chain["agent"] = self.agent_name
                attack_chains.append(chain)

        return {"attack_chains": attack_chains}

    def _build_finding_graph(self, findings: list[dict]) -> dict[int, list[tuple[int, str]]]:
        """Build a graph of findings with 'enables' relationships based on category heuristics."""
        graph: dict[int, list[tuple[int, str]]] = {}

        # Define which categories can enable others
        enables_rules = {
            "secret": ["authentication", "authorization", "injection"],
            "configuration": ["secret", "code_execution", "injection"],
            "dependency": ["code_execution", "injection", "deserialization"],
            "injection": ["code_execution", "authorization"],
            "authentication": ["authorization"],
            "input_validation": ["injection", "xss", "path_traversal", "ssrf"],
            "code_execution": ["secret", "authorization"],
        }

        for i, src in enumerate(findings):
            src_cat = src.get("category", "")
            target_cats = enables_rules.get(src_cat, [])
            if not target_cats:
                continue

            for j, tgt in enumerate(findings):
                if i == j:
                    continue
                tgt_cat = tgt.get("category", "")
                if tgt_cat in target_cats:
                    # Check if they share a file or are in the same service
                    same_file = (
                        src.get("file_path", "") == tgt.get("file_path", "")
                        and src.get("file_path", "") != ""
                    )
                    relationship = "enables"
                    if same_file:
                        relationship = "enables_same_component"

                    if i not in graph:
                        graph[i] = []
                    graph[i].append((j, relationship))

        return graph
