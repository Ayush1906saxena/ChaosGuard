"""Route extractor for DAST probing.

Queries ChromaDB for endpoint annotations and extracts HTTP method,
path, params, and auth requirements to produce a structured route manifest.
"""
import logging
import re

import chromadb
import httpx

from config import config

logger = logging.getLogger(__name__)

# Patterns to detect HTTP endpoint annotations
ENDPOINT_PATTERNS = [
    # Spring Boot
    re.compile(r'@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']', re.IGNORECASE),
    # Express.js / Fastify / Koa
    re.compile(r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    # Flask / FastAPI
    re.compile(r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    # Go net/http
    re.compile(r'(?:Handle|HandleFunc)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    # Ruby on Rails
    re.compile(r'(?:get|post|put|patch|delete)\s+["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'(?:resources?|namespace|scope)\s+[:\'](\w+)', re.IGNORECASE),
    # Django
    re.compile(r'path\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    # Sinatra
    re.compile(r'(?:get|post|put|patch|delete)\s+["\']([^"\']+)["\']', re.IGNORECASE),
]


class RouteExtractor:
    """Extracts HTTP routes from indexed code chunks."""

    def __init__(self):
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

    async def extract(self, scan_id: str) -> list[dict]:
        """Query ChromaDB for endpoint annotations and extract routes."""
        routes = []

        try:
            collection = self.chroma_client.get_collection(f"scan_{scan_id.replace('-', '_')}")

            # Search for endpoint-related code
            queries = [
                "@GetMapping @PostMapping @RequestMapping REST endpoint",
                "app.get app.post router.get router.post Express route",
                "@app.get @app.post FastAPI Flask route",
                "HandleFunc Handle http endpoint",
                "resources routes get post put delete Rails route",
                "path urlpatterns Django URL route",
                "namespace scope mount API route endpoint",
            ]

            seen_paths = set()
            for query in queries:
                query_embedding = await self._embed_query(query)
                results = collection.query(query_embeddings=[query_embedding], n_results=20)
                if not results or not results["documents"]:
                    continue

                for i, doc in enumerate(results["documents"][0]):
                    for pattern in ENDPOINT_PATTERNS:
                        for match in pattern.finditer(doc):
                            groups = match.groups()
                            if len(groups) == 2:
                                method, path = groups
                            elif len(groups) == 1:
                                method, path = "GET", groups[0]
                            else:
                                continue

                            method = method.upper()
                            if method == "REQUESTMAPPING":
                                method = "GET"  # Default

                            if path not in seen_paths:
                                seen_paths.add(path)
                                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                                routes.append({
                                    "method": method,
                                    "path": path,
                                    "file": meta.get("file_path", "unknown"),
                                    "params": self._extract_params(path),
                                    "auth_required": self._detect_auth(doc),
                                })

        except Exception as exc:
            logger.warning("Route extraction failed: %s", exc)

        logger.info("Extracted %d routes for scan %s", len(routes), scan_id)
        return routes

    def _extract_params(self, path: str) -> list[str]:
        """Extract path parameters like {id} or :id."""
        params = re.findall(r'\{(\w+)\}', path)
        params.extend(re.findall(r':(\w+)', path))
        return params

    def _detect_auth(self, code: str) -> bool:
        """Heuristic: detect if endpoint requires authentication."""
        auth_indicators = [
            "@PreAuthorize", "@Secured", "@RolesAllowed",
            "authenticated", "authorize", "jwt", "token",
            "requireAuth", "isAuthenticated", "passport",
        ]
        code_lower = code.lower()
        return any(ind.lower() in code_lower for ind in auth_indicators)
