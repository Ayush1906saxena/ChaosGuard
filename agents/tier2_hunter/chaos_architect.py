from .base_agent import BaseAgent
from config import config


class ChaosArchitect(BaseAgent):
    def __init__(self):
        super().__init__("chaos_architect", "chaos_architect_system.txt", config.REASONING_MODEL)

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        queries = [
            "HTTP client external API call service",
            "database connection pool datasource",
            "circuit breaker retry timeout fallback",
            "message queue kafka rabbit producer consumer",
            "health check endpoint actuator readiness liveness",
            "cache redis memcached",
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

        prompt = (
            f"Analyze the following code for resilience issues, missing fault tolerance patterns, "
            f"and potential cascade failures.\n\n"
            f"Repository: {state.get('repo_url', '')}\n"
            f"Languages: {', '.join(state.get('repo_metadata', {}).get('languages', []))}\n\n"
            f"{self._format_chunks(unique[:config.MAX_CONTEXT_CHUNKS])}"
        )

        result = await ollama_client.generate(prompt, self.system_prompt, model=self.model, expect_json=True)
        findings = []
        chaos_scenarios = []
        if isinstance(result, dict):
            parsed = result.get("parsed", {})
            for f in parsed.get("findings", []):
                f["agent"] = self.agent_name
                f["discovered_tier"] = "HUNTER"
                findings.append(f)
            chaos_scenarios = parsed.get("chaos_scenarios", [])

        return {"findings": findings, "chaos_scenarios": chaos_scenarios}
