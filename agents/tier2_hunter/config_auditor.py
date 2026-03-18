from .base_agent import BaseAgent
from config import config


class ConfigAuditor(BaseAgent):
    def __init__(self):
        super().__init__("config_auditor", "config_auditor_system.txt", config.REASONING_MODEL)

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        queries = [
            "Dockerfile FROM RUN EXPOSE USER",
            "docker-compose services volumes ports",
            "kubernetes deployment pod container securityContext",
            "CI CD pipeline workflow github actions",
            "nginx apache server configuration",
            "terraform provider resource module",
            "helm chart values template",
            "environment variable config settings",
        ]

        all_chunks = []
        for q in queries:
            chunks = await self.rag_search(scan_id, q, n_results=5)
            all_chunks.extend(chunks)

        # Deduplicate
        seen = set()
        unique = []
        for c in all_chunks:
            key = c["content"][:200]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Build context from recon config findings
        recon_config_findings = [
            f for f in state.get("recon_findings", [])
            if f.get("category") == "configuration"
        ]
        recon_context = ""
        if recon_config_findings:
            recon_context = "Recon already identified these configuration issues:\n"
            for rf in recon_config_findings[:15]:
                recon_context += (
                    f"- [{rf.get('severity', 'UNKNOWN')}] {rf.get('title', 'Untitled')} "
                    f"in {rf.get('file_path', 'unknown')}: {rf.get('remediation', '')}\n"
                )
            recon_context += (
                "\nBuild on these findings with deeper context-aware analysis. "
                "Look for issues the deterministic scanner could not catch.\n\n"
            )

        prompt = (
            f"Perform a deep configuration security audit on the following infrastructure "
            f"and deployment configuration files.\n\n"
            f"Repository: {state.get('repo_url', '')}\n"
            f"Languages: {', '.join(state.get('repo_metadata', {}).get('languages', []))}\n"
            f"Frameworks: {', '.join(state.get('repo_metadata', {}).get('frameworks', []))}\n\n"
            f"{recon_context}"
            f"{self._format_chunks(unique[:config.MAX_CONTEXT_CHUNKS])}"
        )

        result = await ollama_client.generate(prompt, self.system_prompt, model=self.model, expect_json=True)
        findings = []
        if isinstance(result, dict):
            parsed = result.get("parsed", {})
            for f in parsed.get("findings", []):
                if not isinstance(f, dict):
                    continue
                f["agent"] = self.agent_name
                f["discovered_tier"] = "HUNTER"
                findings.append(f)

        return {"findings": findings}
