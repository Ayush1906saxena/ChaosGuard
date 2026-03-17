from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Sequence

import httpx
import redis.asyncio as aioredis

from config import config
from chunker.base_chunker import CodeChunk

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days


class Embedder:
    """Generate embeddings via Ollama /api/embed with Redis dedup cache."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=config.OLLAMA_BASE_URL,
            timeout=httpx.Timeout(config.OLLAMA_TIMEOUT_SECONDS),
        )
        self._redis: aioredis.Redis | None = None
        self._batch_size = config.EMBEDDING_BATCH_SIZE
        self._max_retries = config.OLLAMA_MAX_RETRIES

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                config.REDIS_URL, decode_responses=True
            )
        return self._redis

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_cached(self, cache_key: str) -> list[float] | None:
        try:
            rd = await self._get_redis()
            raw = await rd.get(f"emb:{cache_key}")
            if raw:
                return json.loads(raw)
        except Exception:
            logger.debug("Redis cache miss or error for key %s", cache_key)
        return None

    async def _set_cached(self, cache_key: str, embedding: list[float]) -> None:
        try:
            rd = await self._get_redis()
            await rd.set(
                f"emb:{cache_key}",
                json.dumps(embedding),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.debug("Failed to cache embedding for key %s", cache_key)

    async def _call_ollama_single(self, text: str) -> list[float]:
        """Call Ollama /api/embeddings (legacy single-prompt API)."""
        resp = await self._client.post(
            "/api/embeddings",
            json={"model": config.EMBED_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def _call_ollama_batch(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama /api/embed (batch API, v0.15+)."""
        resp = await self._client.post(
            "/api/embed",
            json={"model": config.EMBED_MODEL, "input": texts},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    async def _call_ollama(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama with retry. Auto-detects batch vs legacy API."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                # Try batch API first
                return await self._call_ollama_batch(texts)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    # Fallback to legacy single-prompt API
                    logger.info("Using legacy /api/embeddings endpoint (single prompt)")
                    results = []
                    for text in texts:
                        emb = await self._call_ollama_single(text)
                        results.append(emb)
                    return results
                last_exc = exc
            except Exception as exc:
                last_exc = exc
            wait = 2 ** attempt
            logger.warning(
                "Ollama embed attempt %d/%d failed: %s – retrying in %ds",
                attempt + 1, self._max_retries, last_exc, wait,
            )
            await asyncio.sleep(wait)
        raise RuntimeError(
            f"Ollama embedding failed after {self._max_retries} attempts"
        ) from last_exc

    async def embed_chunks(self, chunks: Sequence[CodeChunk]) -> list[CodeChunk]:
        """Embed a list of chunks, using cache where possible. Returns chunks with embeddings set."""
        # Separate cached vs. uncached
        texts: list[str] = []
        hashes: list[str] = []
        cached_map: dict[int, list[float]] = {}

        for i, chunk in enumerate(chunks):
            text = chunk.to_embedding_text()
            h = self._content_hash(text)
            hashes.append(h)
            cached = await self._get_cached(h)
            if cached is not None:
                cached_map[i] = cached
            else:
                # Truncate to ~2000 chars to avoid Ollama timeouts on CPU
                texts.append(text[:2000] if len(text) > 2000 else text)

        # Build index map for uncached items
        uncached_indices = [i for i in range(len(chunks)) if i not in cached_map]

        # Batch-embed uncached texts
        all_embeddings: list[list[float]] = []
        for batch_start in range(0, len(texts), self._batch_size):
            batch = texts[batch_start : batch_start + self._batch_size]
            try:
                batch_embeddings = await self._call_ollama(batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as exc:
                logger.warning("Batch embed failed (batch %d-%d), using zero vectors: %s",
                             batch_start, batch_start + len(batch), exc)
                # Use zero vectors as fallback so indexing can continue
                all_embeddings.extend([[0.0] * 768 for _ in batch])

        # Assign embeddings back to chunks
        result: list[CodeChunk] = list(chunks)
        embed_idx = 0
        for i in range(len(result)):
            if i in cached_map:
                result[i].embedding = cached_map[i]
            else:
                emb = all_embeddings[embed_idx]
                result[i].embedding = emb
                # Cache the new embedding
                await self._set_cached(hashes[i], emb)
                embed_idx += 1

        return result

    async def close(self) -> None:
        await self._client.aclose()
        if self._redis is not None:
            await self._redis.aclose()
