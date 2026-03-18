from .base_agent import BaseAgent
from config import config


class LoadAnalyzer(BaseAgent):
    def __init__(self):
        super().__init__("load_analyzer", "load_analyzer_system.txt", config.CODE_MODEL)

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        queries = [
            "N+1 query lazy loading findAll",
            "synchronous blocking HTTP call",
            "shared mutable state thread",
            "connection stream close resource leak",
            "loop database query repeated",
            "unbounded list collection memory",
            "thread pool executor concurrent",
            "async await blocking IO",
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
            f"Analyze the following code for performance and load-related issues including "
            f"N+1 queries, blocking calls, resource leaks, and thread safety problems.\n\n"
            f"Repository: {state.get('repo_url', '')}\n"
            f"Languages: {', '.join(state.get('repo_metadata', {}).get('languages', []))}\n"
            f"Frameworks: {', '.join(state.get('repo_metadata', {}).get('frameworks', []))}\n\n"
            f"Recon findings summary:\n{self._format_recon_findings(state.get('recon_findings', []))}\n\n"
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
