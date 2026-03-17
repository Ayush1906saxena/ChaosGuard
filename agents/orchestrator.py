import asyncio
import hashlib
import logging
import time
from typing import TypedDict

import chromadb

from config import config

logger = logging.getLogger(__name__)


class ScanState(TypedDict):
    scan_id: str
    repo_url: str
    tier: str
    repo_metadata: dict
    recon_findings: list
    findings: list
    chaos_scenarios: list
    attack_chains: list
    pentest_playbook: dict
    agent_logs: list
    current_phase: str
    iteration_count: int
    clone_path: str
    target_url: str


class Orchestrator:
    def __init__(self):
        self.hunter_agents = {}
        self.siege_agents = {}

    def _init_hunter_agents(self):
        from tier2_hunter.vulnerability_hunter import VulnerabilityHunter
        from tier2_hunter.chaos_architect import ChaosArchitect
        from tier2_hunter.load_analyzer import LoadAnalyzer
        from tier2_hunter.config_auditor import ConfigAuditor

        self.hunter_agents = {
            "vuln_hunter": VulnerabilityHunter(),
            "chaos_architect": ChaosArchitect(),
            "load_analyzer": LoadAnalyzer(),
            "config_auditor": ConfigAuditor(),
        }

    def _init_siege_agents(self):
        from tier3_siege.attack_chain_constructor import AttackChainConstructor
        from tier3_siege.exploit_analyst import ExploitAnalyst
        from tier3_siege.chaos_cascade_simulator import ChaosCascadeSimulator
        from tier3_siege.business_logic_analyzer import BusinessLogicAnalyzer

        self.siege_agents = {
            "attack_chain": AttackChainConstructor(),
            "exploit_analyst": ExploitAnalyst(),
            "chaos_cascade": ChaosCascadeSimulator(),
            "business_logic": BusinessLogicAnalyzer(),
        }

    def _create_scratchpad(self, scan_id: str):
        """Create a shared scratchpad for inter-agent communication."""
        try:
            from scratchpad import AgentScratchpad
            return AgentScratchpad(scan_id)
        except Exception as exc:
            logger.warning("Could not create scratchpad: %s", exc)
            return None

    def _create_metrics(self, scan_id: str):
        """Create metrics tracker for this scan."""
        try:
            from metrics import ScanMetrics
            return ScanMetrics(scan_id)
        except Exception as exc:
            logger.debug("Could not create metrics tracker: %s", exc)
            return None

    async def run_recon(self, state: ScanState) -> ScanState:
        """Run all Tier 1 Recon scanners against indexed code chunks."""
        state["current_phase"] = "recon"
        start = time.monotonic()
        logger.info("Starting Recon phase for scan %s", state["scan_id"])

        from tier1_recon.secret_scanner import scan_for_secrets
        from tier1_recon.dependency_scanner import scan_dependencies
        from tier1_recon.config_scanner import scan_configs
        from tier1_recon.code_smell_scanner import scan_code_smells

        recon_findings = []

        try:
            chroma_client = chromadb.HttpClient(host=config.CHROMADB_HOST, port=config.CHROMADB_PORT)
            collection = chroma_client.get_collection(f"scan_{state['scan_id'].replace('-', '_')}")

            all_docs = collection.get(include=["documents", "metadatas"])
            documents = all_docs.get("documents", [])
            metadatas = all_docs.get("metadatas", [])

            for i, doc in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                file_path = meta.get("file_path", "unknown")
                file_name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

                recon_findings.extend(scan_for_secrets(file_path, doc, file_name))
                recon_findings.extend(scan_dependencies(file_path, doc, file_name))
                recon_findings.extend(scan_configs(file_path, doc, file_name))
                recon_findings.extend(scan_code_smells(file_path, doc, file_name))

        except Exception as exc:
            logger.error("Failed to retrieve documents from ChromaDB: %s", exc)
            state["agent_logs"].append({
                "agent": "recon",
                "phase": "recon",
                "error": str(exc),
            })

        # Deduplicate recon findings by ID
        seen_ids = set()
        unique_findings = []
        for f in recon_findings:
            fid = f.get("id", "")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                f["discovered_tier"] = "RECON"
                unique_findings.append(f)

        state["recon_findings"] = unique_findings
        state["findings"] = list(unique_findings)
        state["agent_logs"].append({
            "agent": "recon",
            "phase": "recon",
            "findings_count": len(unique_findings),
            "duration_s": round(time.monotonic() - start, 2),
        })

        logger.info("Recon phase complete: %d findings (%.1fs)", len(unique_findings), time.monotonic() - start)
        return state

    async def run_hunter(self, state: ScanState) -> ScanState:
        """Run all Tier 2 Hunter agents in parallel, then cross-reference and dedup."""
        state["current_phase"] = "hunter"
        start = time.monotonic()
        logger.info("Starting Hunter phase for scan %s", state["scan_id"])

        if not self.hunter_agents:
            self._init_hunter_agents()

        # Create scratchpad for inter-agent communication
        scratchpad = self._create_scratchpad(state["scan_id"])

        # Inject scratchpad into agents
        for agent in self.hunter_agents.values():
            agent.scratchpad = scratchpad

        async def run_agent(name: str, agent):
            try:
                if scratchpad:
                    scratchpad.set_agent_status(name, "running")
                result = await agent.analyze(state["scan_id"], state)
                # Post findings to scratchpad as they complete
                if scratchpad:
                    for f in result.get("findings", []):
                        scratchpad.post_finding(name, f.get("title", "untitled"))
                    scratchpad.set_agent_status(name, "complete")
                return name, result
            except Exception as exc:
                logger.error("Hunter agent %s failed: %s", name, exc)
                if scratchpad:
                    scratchpad.set_agent_status(name, "failed")
                state["agent_logs"].append({
                    "agent": name,
                    "phase": "hunter",
                    "error": str(exc),
                })
                return name, {"findings": []}

        tasks = [run_agent(name, agent) for name, agent in self.hunter_agents.items()]
        results = await asyncio.gather(*tasks)

        hunter_findings = []
        chaos_scenarios = []
        for name, result in results:
            agent_findings = result.get("findings", [])
            hunter_findings.extend(agent_findings)
            chaos_scenarios.extend(result.get("chaos_scenarios", []))
            state["agent_logs"].append({
                "agent": name,
                "phase": "hunter",
                "findings_count": len(agent_findings),
            })

        # Run correlator pass using scratchpad (Task 2e)
        if scratchpad:
            correlated = await self._run_correlator(state["scan_id"], scratchpad)
            hunter_findings.extend(correlated)

        hunter_findings = self._cross_reference(hunter_findings)
        hunter_findings = self._dedup_rank(hunter_findings)

        state["findings"] = list(state.get("recon_findings", [])) + hunter_findings
        state["chaos_scenarios"] = chaos_scenarios

        logger.info(
            "Hunter phase complete: %d hunter findings, %d chaos scenarios (%.1fs)",
            len(hunter_findings), len(chaos_scenarios), time.monotonic() - start,
        )
        return state

    async def run_siege(self, state: ScanState) -> ScanState:
        """Run Tier 3 Siege agents: fan out, cross-reference, and final dedup."""
        state["current_phase"] = "siege"
        start = time.monotonic()
        logger.info("Starting Siege phase for scan %s", state["scan_id"])

        if not self.siege_agents:
            self._init_siege_agents()

        scratchpad = self._create_scratchpad(state["scan_id"])
        for agent in self.siege_agents.values():
            agent.scratchpad = scratchpad

        async def run_agent(name: str, agent):
            try:
                if scratchpad:
                    scratchpad.set_agent_status(name, "running")
                result = await agent.analyze(state["scan_id"], state)
                if scratchpad:
                    for f in result.get("findings", []):
                        scratchpad.post_finding(name, f.get("title", "untitled"))
                    scratchpad.set_agent_status(name, "complete")
                return name, result
            except Exception as exc:
                logger.error("Siege agent %s failed: %s", name, exc)
                if scratchpad:
                    scratchpad.set_agent_status(name, "failed")
                state["agent_logs"].append({
                    "agent": name,
                    "phase": "siege",
                    "error": str(exc),
                })
                return name, {"findings": []}

        tasks = [run_agent(name, agent) for name, agent in self.siege_agents.items()]
        results = await asyncio.gather(*tasks)

        siege_findings = []
        attack_chains = []
        pentest_playbook = {}
        chaos_scenarios = list(state.get("chaos_scenarios", []))

        for name, result in results:
            agent_findings = result.get("findings", [])
            siege_findings.extend(agent_findings)
            attack_chains.extend(result.get("attack_chains", []))
            chaos_scenarios.extend(result.get("chaos_scenarios", []))
            if result.get("pentest_playbook"):
                pentest_playbook = result["pentest_playbook"]
            state["agent_logs"].append({
                "agent": name,
                "phase": "siege",
                "findings_count": len(agent_findings),
            })

        # Run correlator pass
        if scratchpad:
            correlated = await self._run_correlator(state["scan_id"], scratchpad)
            siege_findings.extend(correlated)

        all_siege_findings = self._cross_reference(siege_findings)
        all_siege_findings = self._dedup_rank(all_siege_findings)

        all_findings = list(state.get("findings", [])) + all_siege_findings
        all_findings = self._dedup_rank(all_findings)

        state["findings"] = all_findings
        state["attack_chains"] = attack_chains
        state["chaos_scenarios"] = chaos_scenarios
        state["pentest_playbook"] = pentest_playbook

        logger.info(
            "Siege phase complete: %d total findings, %d attack chains, %d chaos scenarios (%.1fs)",
            len(all_findings), len(attack_chains), len(chaos_scenarios), time.monotonic() - start,
        )
        return state

    async def run_live(self, state: ScanState) -> ScanState:
        """Run LIVE tier: DAST probe agents against a target URL after static analysis."""
        state["current_phase"] = "live"
        target_url = state.get("target_url", "")
        if not target_url:
            logger.warning("LIVE tier requested but no target_url provided, skipping DAST")
            return state

        logger.info("Starting LIVE/DAST phase for scan %s against %s", state["scan_id"], target_url)

        try:
            from dast.route_extractor import RouteExtractor
            from dast.idor_agent import IdorAgent
            from dast.auth_bypass_agent import AuthBypassAgent
            from dast.sqli_probe_agent import SqliProbeAgent
            from dast.race_condition_agent import RaceConditionAgent

            # Extract routes from indexed code
            extractor = RouteExtractor()
            routes = await extractor.extract(state["scan_id"])

            dast_agents = {
                "idor": IdorAgent(target_url, routes),
                "auth_bypass": AuthBypassAgent(target_url, routes),
                "sqli_probe": SqliProbeAgent(target_url, routes),
                "race_condition": RaceConditionAgent(target_url, routes),
            }

            dast_findings = []
            for name, agent in dast_agents.items():
                try:
                    result = await agent.run()
                    findings = result.get("findings", [])
                    for f in findings:
                        f["agent"] = f"dast_{name}"
                        f["discovered_tier"] = "LIVE"
                    dast_findings.extend(findings)
                except Exception as exc:
                    logger.error("DAST agent %s failed: %s", name, exc)

            state["findings"] = list(state.get("findings", [])) + dast_findings
            logger.info("LIVE phase complete: %d DAST findings", len(dast_findings))

        except ImportError:
            logger.warning("DAST agents not yet implemented, skipping LIVE phase")
        except Exception as exc:
            logger.error("LIVE phase failed: %s", exc)

        return state

    async def _run_correlator(self, scan_id: str, scratchpad) -> list[dict]:
        """Run a correlator LLM call that reads the full scratchpad and produces correlated findings."""
        try:
            from llm_client import ollama_client

            findings = scratchpad.get_findings()
            signals = scratchpad.get_signals()

            if not findings:
                return []

            prompt = (
                f"You are a security findings correlator. Multiple agents have analyzed a codebase.\n\n"
                f"Agent findings so far:\n"
                + "\n".join(f"- {f}" for f in findings)
                + "\n\n"
            )
            if signals:
                prompt += "Agent signals:\n" + "\n".join(f"- {s}" for s in signals) + "\n\n"

            prompt += (
                "Identify any CORRELATED findings — vulnerability chains where multiple individual "
                "findings combine into a more severe attack. Return JSON with a 'findings' array. "
                "Each finding should have: title, severity, category, description, evidence, "
                "file_path, confidence."
            )

            result = await ollama_client.generate(
                prompt,
                system="You are a security correlation expert. Identify multi-step attacks from individual findings.",
                model=config.REASONING_MODEL,
                expect_json=True,
            )

            correlated = []
            if isinstance(result, dict):
                parsed = result.get("parsed", {})
                for f in parsed.get("findings", []):
                    f["agent"] = "correlator"
                    f["discovered_tier"] = "CORRELATED"
                    correlated.append(f)

            if correlated:
                logger.info("Correlator produced %d correlated findings for scan %s", len(correlated), scan_id)

            return correlated

        except Exception as exc:
            logger.warning("Correlator failed: %s", exc)
            return []

    def _cross_reference(self, findings: list[dict]) -> list[dict]:
        """Cross-reference findings to identify corroborating evidence and increase confidence."""
        if len(findings) < 2:
            return findings

        by_file: dict[str, list[dict]] = {}
        for f in findings:
            fp = f.get("file_path", "")
            fp = str(fp) if fp else ""
            if fp:
                by_file.setdefault(fp, []).append(f)

        by_category: dict[str, list[dict]] = {}
        for f in findings:
            cat = f.get("category", "")
            cat = str(cat) if cat else ""
            if cat:
                by_category.setdefault(cat, []).append(f)

        for f in findings:
            corroborations = []
            fp = str(f.get("file_path", "") or "")
            cat = str(f.get("category", "") or "")

            if fp in by_file:
                for other in by_file[fp]:
                    if (
                        other is not f
                        and other.get("agent") != f.get("agent")
                        and other.get("category") == cat
                    ):
                        corroborations.append({
                            "agent": other.get("agent", "unknown"),
                            "title": other.get("title", ""),
                        })

            related_categories = {
                "injection": ["input_validation", "code_execution"],
                "secret": ["configuration", "cryptography"],
                "authentication": ["authorization", "session"],
                "configuration": ["secret", "dependency"],
            }
            related = related_categories.get(cat, [])
            for rel_cat in related:
                if rel_cat in by_category:
                    for other in by_category[rel_cat]:
                        if other is not f and other.get("file_path") == fp:
                            corroborations.append({
                                "agent": other.get("agent", "unknown"),
                                "related_category": rel_cat,
                                "title": other.get("title", ""),
                            })

            if corroborations:
                f["corroborated_by"] = corroborations
                f["confidence"] = min(f.get("confidence", 70) + len(corroborations) * 10, 100)

        return findings

    def _dedup_rank(self, findings: list[dict]) -> list[dict]:
        """Deduplicate by similarity, apply FP suppression, and rank by severity."""
        if not findings:
            return []

        # Load FP suppression fingerprints (Task 3e)
        suppression_fps = set()
        try:
            from feedback_client import get_suppression_fingerprints
            suppression_fps = get_suppression_fingerprints()
        except Exception:
            pass

        seen = set()
        unique = []
        for f in findings:
            # Ensure hashable values for dedup keys
            file_path = str(f.get("file_path", ""))
            title = str(f.get("title", ""))
            line = str(f.get("line", ""))
            category = str(f.get("category", ""))
            evidence = f.get("evidence", "")
            if isinstance(evidence, list):
                evidence = str(evidence)
            evidence = str(evidence) if evidence else ""

            key1 = (file_path, title, line)
            key2 = (file_path, category, evidence[:80])

            if key1 in seen or key2 in seen:
                continue
            seen.add(key1)
            seen.add(key2)

            # Auto-downgrade confidence for known FP patterns (Task 3e)
            if suppression_fps:
                code_content = f.get("evidence", "") or f.get("affected_code", "")
                if code_content:
                    fp_hash = hashlib.sha256(
                        (code_content + "|" + f.get("category", "") + "|" + f.get("file_path", "")).encode()
                    ).hexdigest()
                    if fp_hash in suppression_fps:
                        f["confidence"] = f.get("confidence", 50) * 0.3
                        f["fp_suppressed"] = True

            unique.append(f)

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}
        unique.sort(key=lambda f: (
            severity_order.get(f.get("severity", "unknown").lower(), 5),
            -(f.get("confidence", 50)),
        ))

        return unique

    async def run(
        self,
        scan_id: str,
        tier: str,
        repo_url: str,
        repo_metadata: dict,
        recon_findings: list,
        clone_path: str = "",
        target_url: str = "",
    ) -> ScanState:
        state: ScanState = {
            "scan_id": scan_id,
            "repo_url": repo_url,
            "tier": tier.upper(),
            "repo_metadata": repo_metadata,
            "recon_findings": recon_findings,
            "findings": list(recon_findings),
            "chaos_scenarios": [],
            "attack_chains": [],
            "pentest_playbook": {},
            "agent_logs": [],
            "current_phase": "init",
            "iteration_count": 0,
            "clone_path": clone_path,
            "target_url": target_url,
        }

        # Record metrics
        metrics = self._create_metrics(scan_id)
        if metrics:
            metrics.record_phase_start("total")
            # Wire metrics into LLM client for call duration tracking
            try:
                from llm_client import ollama_client
                ollama_client.set_metrics(metrics)
            except Exception:
                pass

        if tier.upper() == "RECON":
            state = await self.run_recon(state)
        elif tier.upper() == "HUNTER":
            state = await self.run_recon(state)
            state = await self.run_hunter(state)
        elif tier.upper() == "LIVE":
            state = await self.run_recon(state)
            state = await self.run_hunter(state)
            state = await self.run_siege(state)
            state = await self.run_live(state)
        else:  # SIEGE
            state = await self.run_recon(state)
            state = await self.run_hunter(state)
            state = await self.run_siege(state)

        # Flush metrics
        if metrics:
            metrics.record_phase_end("total")
            metrics.record_finding_counts(state["findings"])
            metrics.flush_to_db(scan_id, tier)
            # Clear metrics from LLM client
            try:
                from llm_client import ollama_client
                ollama_client.set_metrics(None)
            except Exception:
                pass

        return state
