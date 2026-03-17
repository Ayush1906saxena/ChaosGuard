import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PlaybookGenerator:
    """Generates a structured penetration testing playbook from Siege-tier analysis."""

    def generate(
        self,
        scan_id: str,
        repo_url: str,
        findings: list[dict],
        attack_chains: list[dict] = None,
        pentest_playbook: dict = None,
    ) -> dict:
        """Aggregate PoCs from exploit analyst and structure into ordered test cases."""
        # Collect all PoC-enriched findings
        poc_findings = [f for f in findings if f.get("poc")]

        # Collect test cases from exploit analyst playbook if available
        existing_test_cases = []
        if pentest_playbook and "test_cases" in pentest_playbook:
            existing_test_cases = pentest_playbook["test_cases"]

        # Build structured playbook
        test_cases = []
        seen_titles = set()

        # First, include existing test cases from exploit analyst
        for tc in existing_test_cases:
            title = tc.get("title", "")
            if title not in seen_titles:
                seen_titles.add(title)
                test_cases.append(tc)

        # Then add any PoC findings not already covered
        for finding in poc_findings:
            title = finding.get("title", "")
            if title in seen_titles:
                continue
            seen_titles.add(title)

            test_cases.append({
                "test_id": f"TC-{len(test_cases) + 1:03d}",
                "title": title,
                "severity": finding.get("severity", "UNKNOWN"),
                "category": finding.get("category", "unknown"),
                "owasp": finding.get("owasp", {}),
                "mitre": finding.get("mitre", {}),
                "target_file": finding.get("file_path", "unknown"),
                "target_line": finding.get("line", "N/A"),
                "poc": finding["poc"],
                "prerequisites": finding.get("prerequisites", ["Access to target application"]),
                "tools_required": finding.get("tools_required", ["Burp Suite", "curl"]),
            })

        # Order test cases by severity priority
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        test_cases.sort(key=lambda tc: severity_order.get(tc.get("severity", "info").lower(), 5))

        # Re-number after sorting
        for i, tc in enumerate(test_cases):
            tc["test_id"] = f"TC-{i + 1:03d}"

        # Build attack chain test sequences
        chain_sequences = []
        if attack_chains:
            for chain in attack_chains:
                chain_sequences.append({
                    "chain_title": chain.get("title", "Unnamed Chain"),
                    "steps": chain.get("steps", []),
                    "impact": chain.get("impact", "Unknown"),
                    "likelihood": chain.get("likelihood", "MEDIUM"),
                })

        # Determine scope and methodology
        categories_in_scope = list({tc.get("category", "unknown") for tc in test_cases})
        tools_aggregate = list({
            tool
            for tc in test_cases
            for tool in tc.get("tools_required", [])
        })

        playbook = {
            "playbook_id": f"PB-{scan_id[:8]}",
            "generated_at": datetime.utcnow().isoformat(),
            "scope": {
                "target": repo_url,
                "categories_in_scope": categories_in_scope,
                "total_test_cases": len(test_cases),
                "critical_count": sum(1 for tc in test_cases if tc.get("severity", "").lower() == "critical"),
                "high_count": sum(1 for tc in test_cases if tc.get("severity", "").lower() == "high"),
            },
            "methodology": "OWASP Testing Guide v4.2 + MITRE ATT&CK Framework + PTES",
            "prerequisites": [
                "Authorized access to the target application and source code",
                "Test environment isolated from production",
                "Multiple test user accounts with varying privilege levels",
                "Network access to application endpoints",
                "Burp Suite Professional or equivalent proxy tool",
            ],
            "tools_required": sorted(tools_aggregate),
            "test_cases": test_cases,
            "attack_chain_sequences": chain_sequences,
            "execution_notes": {
                "order": "Execute test cases in the order listed (critical first).",
                "documentation": "Document all findings with screenshots and request/response pairs.",
                "rollback": "Ensure all test data is cleaned up after testing.",
                "reporting": "Report critical and high findings immediately to the development team.",
            },
        }

        return playbook
