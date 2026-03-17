import os
import logging

import chromadb
import httpx
import psycopg2
import psycopg2.extras

from config import config

logger = logging.getLogger(__name__)


async def _ollama_embed(text: str) -> list[float]:
    """Compute an embedding via Ollama using the same model as the indexer."""
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


class BaseAgent:
    def __init__(self, agent_name: str, system_prompt_file: str, model: str = None):
        self.agent_name = agent_name
        self.model = model or config.CODE_MODEL
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", system_prompt_file)
        with open(prompt_path) as f:
            self.system_prompt = f.read()
        self.chroma_client = chromadb.HttpClient(host=config.CHROMADB_HOST, port=config.CHROMADB_PORT)
        self.scratchpad = None

    async def rag_search(self, scan_id: str, query: str, n_results: int = 10, language: str = None) -> list[dict]:
        collection = self.chroma_client.get_collection(f"scan_{scan_id.replace('-', '_')}")
        where_filter = {"language": language} if language else None
        query_embedding = await _ollama_embed(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=n_results, where=where_filter)
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "content": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })
        return chunks

    async def rag_search_with_context(
        self, scan_id: str, query: str, n_results: int = 10, expand_hops: int = 1
    ) -> list[dict]:
        """RAG search enriched with call graph neighbors."""
        # Step 1: Initial RAG search
        chunks = await self.rag_search(scan_id, query, n_results)
        if not chunks:
            return chunks

        # Step 2: Extract function names from chunk metadata
        function_names = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            name = meta.get("name", "")
            if name and meta.get("chunk_type") in ("method", "function", "class"):
                function_names.append(name)

        if not function_names:
            return chunks

        # Step 3: Get call graph neighbors
        neighbor_names = self._get_call_neighbors(scan_id, function_names, expand_hops)
        if not neighbor_names:
            return chunks

        # Step 4: Fetch neighbor chunks from ChromaDB by name
        existing_names = {c.get("metadata", {}).get("name", "") for c in chunks}
        new_names = [n for n in neighbor_names if n not in existing_names]

        if new_names:
            try:
                collection = self.chroma_client.get_collection(f"scan_{scan_id.replace('-', '_')}")
                for name in new_names[:10]:  # Limit to 10 neighbors
                    name_embedding = await _ollama_embed(name)
                    results = collection.query(
                        query_embeddings=[name_embedding],
                        n_results=2,
                        where={"name": name},
                    )
                    if results and results["documents"] and results["documents"][0]:
                        for i, doc in enumerate(results["documents"][0]):
                            meta = results["metadatas"][0][i] if results["metadatas"] else {}
                            # Determine call relationship
                            orig_name = meta.get("name", "")
                            relation = "callee" if orig_name in neighbor_names else "caller"
                            chunks.append({
                                "content": doc,
                                "metadata": {**meta, "call_relation": relation},
                                "distance": results["distances"][0][i] if results["distances"] else 0,
                            })
            except Exception as exc:
                logger.warning("Failed to fetch neighbor chunks: %s", exc)

        # Deduplicate by chunk content prefix
        seen = set()
        deduped = []
        for c in chunks:
            key = c["content"][:200]
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return deduped

    def _get_call_neighbors(self, scan_id: str, function_names: list[str], hops: int) -> list[str]:
        """Query dependency_graph for callers/callees within N hops."""
        neighbors = set()
        current_names = set(function_names)

        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    for _ in range(hops):
                        if not current_names:
                            break
                        placeholders = ",".join(["%s"] * len(current_names))
                        # Get callees
                        cur.execute(
                            f"SELECT DISTINCT target_name FROM dependency_graph "
                            f"WHERE scan_id = %s AND source_name IN ({placeholders})",
                            [scan_id] + list(current_names),
                        )
                        callees = {row["target_name"] for row in cur.fetchall()}

                        # Get callers
                        cur.execute(
                            f"SELECT DISTINCT source_name FROM dependency_graph "
                            f"WHERE scan_id = %s AND target_name IN ({placeholders})",
                            [scan_id] + list(current_names),
                        )
                        callers = {row["source_name"] for row in cur.fetchall()}

                        new_names = (callees | callers) - neighbors - set(function_names)
                        neighbors.update(new_names)
                        current_names = new_names
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Failed to query call graph: %s", exc)

        return list(neighbors)

    async def analyze(self, scan_id: str, state: dict) -> dict:
        raise NotImplementedError

    def _format_chunks(self, chunks: list[dict]) -> str:
        from prompt_sanitizer import wrap_code_with_delimiters

        parts = []
        for i, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            file_path = meta.get("file_path", "unknown")
            content = chunk["content"]
            call_relation = meta.get("call_relation", "")
            relation_tag = f" [{call_relation}]" if call_relation else ""

            wrapped = wrap_code_with_delimiters(content, f"{file_path}{relation_tag}")
            parts.append(f"--- Chunk {i+1} ---\n{wrapped}\n")
        return "\n".join(parts)

    def _format_recon_findings(self, findings: list[dict]) -> str:
        if not findings:
            return "No Recon findings."
        lines = []
        for f in findings[:20]:
            lines.append(f"- [{f.get('severity', 'UNKNOWN')}] {f.get('title', 'Untitled')}")
        return "\n".join(lines)

    def _get_scratchpad_context(self) -> str:
        """Get formatted context from the shared agent scratchpad."""
        if self.scratchpad is None:
            return ""

        try:
            findings = self.scratchpad.get_findings()
            signals = self.scratchpad.get_signals()

            if not findings and not signals:
                return ""

            parts = ["=== SHARED AGENT CONTEXT ==="]
            if findings:
                parts.append("Other agents have found:")
                for f in findings[-10:]:  # Last 10 findings
                    parts.append(f"  - {f}")
            if signals:
                parts.append("Signals from other agents:")
                for s in signals[-5:]:
                    parts.append(f"  - {s}")
            parts.append("=== END SHARED CONTEXT ===")
            return "\n".join(parts)
        except Exception as exc:
            logger.warning("Failed to read scratchpad: %s", exc)
            return ""

    def _get_fp_patterns(self, scan_id: str, subcategory: str) -> str:
        """Fetch false positive patterns for this subcategory."""
        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT ff.code_fingerprint, f.title, f.evidence, ff.user_comment
                        FROM finding_feedback ff
                        JOIN findings f ON f.id = ff.finding_id
                        WHERE ff.label = 'false_positive'
                          AND f.subcategory = %s
                        ORDER BY ff.created_at DESC
                        LIMIT 5
                        """,
                        (subcategory,),
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()

            if not rows:
                return ""

            parts = ["=== KNOWN FALSE POSITIVE PATTERNS ==="]
            parts.append("The following patterns were previously marked as false positives by users.")
            parts.append("Avoid reporting similar patterns unless you have strong new evidence.\n")
            for row in rows:
                parts.append(f"- Title: {row['title']}")
                if row.get("evidence"):
                    parts.append(f"  Evidence: {row['evidence'][:200]}")
                if row.get("user_comment"):
                    parts.append(f"  User note: {row['user_comment']}")
                parts.append("")
            parts.append("=== END FALSE POSITIVE PATTERNS ===")
            return "\n".join(parts)
        except Exception:
            return ""
