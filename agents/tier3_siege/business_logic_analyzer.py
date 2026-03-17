import logging
import os
from typing import Any

import chromadb
import httpx

from config import config

logger = logging.getLogger(__name__)


class BusinessLogicAnalyzer:
    def __init__(self):
        self.agent_name = "business_logic_analyzer"
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "business_logic_system.txt")
        with open(prompt_path) as f:
            self.system_prompt = f.read()
        self.model = config.REASONING_MODEL
        self.chroma_client = chromadb.HttpClient(host=config.CHROMADB_HOST, port=config.CHROMADB_PORT)

    async def _embed_query(self, text: str) -> list[float]:
        async with httpx.AsyncClient(
            base_url=config.OLLAMA_BASE_URL,
            timeout=httpx.Timeout(60.0),
        ) as client:
            resp = await client.post(
                "/api/embed",
                json={"model": config.EMBED_MODEL, "input": [text[:2000]]},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]

    async def rag_search(self, scan_id: str, query: str, n_results: int = 10) -> list[dict]:
        collection = self.chroma_client.get_collection(f"scan_{scan_id.replace('-', '_')}")
        query_embedding = await self._embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "content": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })
        return chunks

    def _format_chunks(self, chunks: list[dict]) -> str:
        parts = []
        for i, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            parts.append(f"--- Chunk {i+1} [{meta.get('file_path', 'unknown')}] ---\n{chunk['content']}\n")
        return "\n".join(parts)

    async def analyze(self, scan_id: str, state: dict) -> dict:
        from llm_client import ollama_client

        # RAG queries targeting business logic patterns
        business_logic_queries = [
            "user role permission access control check authorization",
            "payment checkout billing charge refund transaction",
            "state machine status transition workflow lifecycle",
            "rate limit throttle quota usage count",
            "inventory stock quantity reserve balance",
            "user registration signup onboarding verification email",
            "order process cart purchase fulfillment shipping",
            "discount coupon promotion pricing calculation",
            "session management cookie token expiry timeout",
            "data export download import upload file access",
        ]

        all_chunks = []
        for query in business_logic_queries:
            chunks = await self.rag_search(scan_id, query, n_results=5)
            all_chunks.extend(chunks)

        # Deduplicate
        seen = set()
        unique = []
        for c in all_chunks:
            key = c["content"][:200]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        if not unique:
            return {"findings": []}

        # Analyze for business logic vulnerabilities
        analysis_categories = [
            {
                "name": "Race Conditions & TOCTOU",
                "focus": (
                    "Look for time-of-check to time-of-use (TOCTOU) vulnerabilities, "
                    "race conditions in balance checks, inventory updates, or concurrent "
                    "transaction processing without proper locking."
                ),
            },
            {
                "name": "IDOR & Broken Object-Level Authorization",
                "focus": (
                    "Look for direct object references where user-supplied IDs are used "
                    "to access resources without verifying the requesting user owns or "
                    "has permission to access that resource."
                ),
            },
            {
                "name": "Business Rule Bypass",
                "focus": (
                    "Look for ways to bypass business rules such as: applying discounts "
                    "multiple times, skipping payment verification, modifying order totals "
                    "client-side, bypassing rate limits, or abusing referral systems."
                ),
            },
            {
                "name": "State Machine Violations",
                "focus": (
                    "Look for state machine logic where transitions between states are not "
                    "properly validated, allowing skipping steps (e.g., going from 'cart' "
                    "to 'shipped' without 'paid'), or reversing irreversible actions."
                ),
            },
        ]

        all_findings = []
        for category in analysis_categories:
            prompt = (
                f"Analyze the following code from {state.get('repo_url', 'the target repository')} "
                f"for {category['name']} vulnerabilities.\n\n"
                f"Focus: {category['focus']}\n\n"
                f"Languages: {', '.join(state.get('repo_metadata', {}).get('languages', []))}\n"
                f"Frameworks: {', '.join(state.get('repo_metadata', {}).get('frameworks', []))}\n\n"
                f"{self._format_chunks(unique[:config.MAX_CONTEXT_CHUNKS])}\n\n"
                f"Return JSON with a 'findings' array. Each finding must have: "
                f"title, severity, category, description, file_path, evidence, remediation, "
                f"and affected_files."
            )

            result = await ollama_client.generate(prompt, self.system_prompt, model=self.model, expect_json=True)
            if isinstance(result, dict):
                parsed = result.get("parsed", {})
                for f in parsed.get("findings", []):
                    f["agent"] = self.agent_name
                    f["discovered_tier"] = "SIEGE"
                    f["analysis_category"] = category["name"]
                    all_findings.append(f)

        return {"findings": all_findings}
