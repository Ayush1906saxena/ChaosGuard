from datetime import datetime


class ReportGenerator:
    def generate(
        self,
        scan_id: str,
        tier: str,
        repo_url: str,
        findings: list,
        chaos_scenarios: list = None,
        attack_chains: list = None,
        pentest_playbook: dict = None,
    ) -> dict:
        severity_counts = {}
        category_counts = {}
        tier_counts = {}
        for f in findings:
            sev = f.get("severity", "UNKNOWN")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            cat = f.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            t = f.get("discovered_tier", "UNKNOWN")
            tier_counts[t] = tier_counts.get(t, 0) + 1

        report = {
            "scan_id": scan_id,
            "tier": tier,
            "repo_url": repo_url,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_findings": len(findings),
                "by_severity": severity_counts,
                "by_category": category_counts,
                "by_tier": tier_counts,
                "top_risk_areas": self._get_top_risk_areas(findings),
            },
            "findings": findings,
        }
        if tier in ("HUNTER", "SIEGE") and chaos_scenarios:
            report["chaos_scenarios"] = chaos_scenarios
        if tier == "SIEGE":
            if attack_chains:
                report["attack_chains"] = attack_chains
            if pentest_playbook:
                report["pentest_playbook"] = pentest_playbook

        return report

    def _get_top_risk_areas(self, findings: list) -> list[str]:
        file_risk = {}
        for f in findings:
            for af in f.get("affected_files", []):
                path = af if isinstance(af, str) else af.get("path", "")
                sev_weight = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1, "INFO": 0}
                file_risk[path] = file_risk.get(path, 0) + sev_weight.get(
                    f.get("severity", "LOW").upper(), 1
                )
            # Also count the primary file_path
            primary = f.get("file_path", "")
            if primary:
                sev_weight = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1, "INFO": 0}
                file_risk[primary] = file_risk.get(primary, 0) + sev_weight.get(
                    f.get("severity", "LOW").upper(), 1
                )
        sorted_files = sorted(file_risk.items(), key=lambda x: x[1], reverse=True)
        return [f[0] for f in sorted_files[:10]]
