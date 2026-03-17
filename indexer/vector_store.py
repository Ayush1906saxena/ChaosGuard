from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings

from config import config
from chunker.base_chunker import CodeChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """Thin wrapper around ChromaDB for storing and querying code chunk embeddings."""

    def __init__(self) -> None:
        self._client = chromadb.HttpClient(
            host=config.CHROMADB_HOST,
            port=config.CHROMADB_PORT,
            settings=Settings(anonymized_telemetry=False),
        )

    def _collection_name(self, scan_id: str) -> str:
        # ChromaDB collection names must match [a-zA-Z0-9_-] and be 3-63 chars
        safe = scan_id.replace("-", "_")
        name = f"scan_{safe}"
        return name[:63]

    def _get_or_create_collection(self, scan_id: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=self._collection_name(scan_id),
            metadata={"hnsw:space": "cosine"},
        )

    def store_chunks(self, scan_id: str, chunks: list[CodeChunk]) -> int:
        """Store chunks with their embeddings in ChromaDB. Returns count stored."""
        if not chunks:
            return 0

        collection = self._get_or_create_collection(scan_id)

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            if chunk.embedding is None:
                logger.warning("Skipping chunk %s – no embedding", chunk.chunk_id)
                continue

            ids.append(chunk.chunk_id)
            embeddings.append(chunk.embedding)
            documents.append(chunk.content)
            metadatas.append({
                "file_path": chunk.file_path,
                "language": chunk.language,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "parent_chunk_id": chunk.parent_chunk_id or "",
                "is_taint_source": chunk.is_taint_source,
                "is_taint_sink": chunk.is_taint_sink,
            })

        if not ids:
            return 0

        # ChromaDB upsert in batches of 5000 (ChromaDB default limit)
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        stored = len(ids)
        logger.info("Stored %d chunks for scan %s", stored, scan_id)
        return stored

    def search(
        self,
        scan_id: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks by embedding vector. Returns list of result dicts."""
        collection = self._get_or_create_collection(scan_id)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        output: list[dict[str, Any]] = []
        if results and results["ids"]:
            for i, chunk_id in enumerate(results["ids"][0]):
                output.append({
                    "chunk_id": chunk_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })

        return output

    def delete_collection(self, scan_id: str) -> None:
        """Delete a scan's entire collection."""
        name = self._collection_name(scan_id)
        try:
            self._client.delete_collection(name)
            logger.info("Deleted collection %s", name)
        except Exception:
            logger.debug("Collection %s not found or already deleted", name)
