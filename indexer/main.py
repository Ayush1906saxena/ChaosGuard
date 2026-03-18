from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from confluent_kafka import Consumer, Producer, KafkaError

from config import config
from chunker.router import chunk_file, detect_language
from chunker.base_chunker import CodeChunk
from embedder import Embedder
from vector_store import VectorStore
from deep_analysis.call_graph import CallGraphTracer
from deep_analysis.data_flow import DataFlowTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("indexer")

# ------------------------------------------------------------------ globals
embedder = Embedder()
vector_store = VectorStore()
call_graph_tracer = CallGraphTracer()
data_flow_tracker = DataFlowTracker()

kafka_producer: Producer | None = None
kafka_consumer_thread: threading.Thread | None = None
_shutdown_event = threading.Event()

# File extensions we index
INDEXABLE_EXTENSIONS = {
    ".java", ".py", ".js", ".jsx", ".ts", ".tsx", ".go",
    ".yml", ".yaml", ".xml", ".json", ".properties",
    ".gradle", ".kt", ".scala", ".rb", ".php", ".cs",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".swift",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".idea", ".vscode",
    "target", "build", "dist", ".gradle", "vendor", ".tox",
    "venv", ".venv", "env",
}

# Files to skip — lock files, minified bundles, generated code
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "Gemfile.lock", "Pipfile.lock",
    "poetry.lock", "cargo.lock", "go.sum",
    ".DS_Store", "thumbs.db",
}

# Skip files matching these patterns (checked via endswith)
SKIP_FILE_SUFFIXES = (".min.js", ".min.css", ".map", ".bundle.js")


# ------------------------------------------------------------------ models
class IndexRequest(BaseModel):
    model_config = {"populate_by_name": True}

    scan_id: str = Field(alias="scanId", default="")
    repo_url: str = Field(alias="repoUrl", default="")
    clone_path: str = Field(alias="clonePath", default="")
    tier: str = "STRIKE"  # RECON | STRIKE | SIEGE
    branch: str = "main"


class IndexResponse(BaseModel):
    scan_id: str
    status: str
    total_files: int
    total_chunks: int
    total_embedded: int
    deep_analysis: dict[str, Any] | None = None


# ------------------------------------------------------------------ helpers

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per-file limit


def _collect_files(clone_path: str) -> list[str]:
    """Walk the clone directory and collect indexable files."""
    files: list[str] = []
    base = Path(clone_path)
    if not base.exists():
        logger.error("Clone path does not exist: %s", clone_path)
        return files

    for root, dirs, filenames in os.walk(base):
        # Prune skipped directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = os.path.join(root, fname)

            # Reject symlinks
            if os.path.islink(fpath):
                logger.warning("Skipping symlink: %s", fpath)
                continue

            # Reject files > 5MB
            try:
                if os.path.getsize(fpath) > MAX_FILE_SIZE:
                    logger.warning("Skipping oversized file (>5MB): %s", fpath)
                    continue
            except OSError:
                continue

            # Skip known non-useful files
            if fname.lower() in SKIP_FILES:
                continue
            if any(fname.lower().endswith(s) for s in SKIP_FILE_SUFFIXES):
                continue

            ext = os.path.splitext(fname)[1].lower()
            if ext in INDEXABLE_EXTENSIONS:
                files.append(fpath)
    return files


def _read_file_safe(path: str) -> str | None:
    """Read a file, returning None on failure. Rejects binary files."""
    try:
        # Reject symlinks at read time as well
        if os.path.islink(path):
            logger.warning("Skipping symlink at read time: %s", path)
            return None

        # Check for binary content (null byte in first 8KB)
        with open(path, "rb") as bf:
            header = bf.read(8192)
            if b"\x00" in header:
                logger.warning("Skipping binary file: %s", path)
                return None

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        logger.warning("Could not read file: %s", path, exc_info=True)
        return None


def _get_producer() -> Producer:
    global kafka_producer
    if kafka_producer is None:
        kafka_producer = Producer({
            "bootstrap.servers": config.KAFKA_BOOTSTRAP,
            "client.id": "indexer-producer",
        })
    return kafka_producer


def _publish_event(topic: str, event: dict[str, Any]) -> None:
    producer = _get_producer()
    producer.produce(
        topic,
        value=json.dumps(event).encode("utf-8"),
    )
    producer.flush(timeout=5)


async def _run_indexing(request: IndexRequest) -> IndexResponse:
    """Core indexing pipeline."""
    scan_id = request.scan_id
    tier = request.tier.upper()
    clone_path = request.clone_path

    logger.info("Starting indexing for scan %s (tier=%s, path=%s)", scan_id, tier, clone_path)

    # 1. Collect files
    file_paths = _collect_files(clone_path)
    logger.info("Found %d indexable files for scan %s", len(file_paths), scan_id)

    # 2. Parse and chunk all files
    all_chunks: list[CodeChunk] = []
    for fpath in file_paths:
        content = _read_file_safe(fpath)
        if content is None:
            continue
        # Use relative path from clone root for file_path in chunks
        rel_path = os.path.relpath(fpath, clone_path)
        try:
            chunks = chunk_file(content, rel_path, scan_id)
            all_chunks.extend(chunks)
        except Exception:
            logger.exception("Failed to chunk file %s", fpath)

    logger.info("Produced %d chunks from %d files for scan %s", len(all_chunks), len(file_paths), scan_id)

    # 3. Embed chunks (all tiers need embeddings for ChromaDB storage)
    total_embedded = 0
    if all_chunks:
        try:
            all_chunks = await embedder.embed_chunks(all_chunks)
            total_embedded = sum(1 for c in all_chunks if c.embedding is not None)
            logger.info("Embedded %d/%d chunks for scan %s", total_embedded, len(all_chunks), scan_id)
        except Exception:
            logger.exception("Embedding failed for scan %s", scan_id)

    # 4. Store in ChromaDB
    chromadb_ok = False
    if total_embedded > 0:
        try:
            vector_store.store_chunks(scan_id, all_chunks)
            chromadb_ok = True
        except Exception:
            logger.exception("ChromaDB storage failed for scan %s", scan_id)

    # 5. Deep analysis for HUNTER and SIEGE tiers
    deep_analysis: dict[str, Any] | None = None
    if tier in ("HUNTER", "SIEGE") and all_chunks:
        try:
            edge_count = call_graph_tracer.build_call_graph(scan_id, all_chunks)
            logger.info("Built call graph with %d edges for scan %s", edge_count, scan_id)

            deep_analysis = {
                "call_graph_edges": edge_count,
            }

            # Data flow analysis only for SIEGE tier
            if tier == "SIEGE":
                call_graph_edges: list[dict[str, Any]] = []
                try:
                    import psycopg2
                    import psycopg2.extras
                    conn = psycopg2.connect(config.POSTGRES_DSN)
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute(
                            "SELECT caller_name, callee_name FROM dependency_graph WHERE scan_id = %s",
                            (scan_id,),
                        )
                        call_graph_edges = [dict(row) for row in cur.fetchall()]
                    conn.close()
                except Exception:
                    logger.warning("Could not fetch call graph edges for data flow", exc_info=True)

                flow_result = data_flow_tracker.analyse(all_chunks, call_graph_edges)
                logger.info(
                    "Data flow analysis: %d sources, %d sinks for scan %s",
                    flow_result["total_sources"], flow_result["total_sinks"], scan_id,
                )
                deep_analysis["data_flow"] = flow_result

                # Tag taint sources and sinks on chunks before storage (1c)
                source_names = {s.get("name", "") for s in flow_result.get("sources", []) if s.get("name")}
                sink_names = {s.get("name", "") for s in flow_result.get("sinks", []) if s.get("name")}
                for chunk in all_chunks:
                    chunk.is_taint_source = chunk.name in source_names
                    chunk.is_taint_sink = chunk.name in sink_names

        except Exception:
            logger.exception("Deep analysis failed for scan %s", scan_id)

    # 6. Publish index-complete event (only if ChromaDB storage succeeded)
    if not chromadb_ok and total_embedded > 0:
        logger.error(
            "Aborting index-complete publish for scan %s — ChromaDB storage failed, "
            "agents would query a non-existent collection", scan_id,
        )
        return IndexResponse(
            scan_id=scan_id,
            status="failed",
            total_files=len(file_paths),
            total_chunks=len(all_chunks),
            total_embedded=0,
            deep_analysis=None,
        )

    index_complete_event = {
        "scan_id": scan_id,
        "status": "complete",
        "total_files": len(file_paths),
        "total_chunks": len(all_chunks),
        "total_embedded": total_embedded,
        "tier": tier,
        "clone_path": clone_path,
        "repo_url": request.repo_url,
        "has_deep_analysis": deep_analysis is not None,
    }
    try:
        # Publish to generic topic for backward compatibility
        _publish_event(config.TOPIC_INDEX_COMPLETE, index_complete_event)

        # Also publish to tier-specific topic for tier workers
        tier_topic_map = {
            "RECON": config.TOPIC_SCAN_RECON,
            "HUNTER": config.TOPIC_SCAN_HUNTER,
            "SIEGE": config.TOPIC_SCAN_SIEGE,
        }
        tier_topic = tier_topic_map.get(tier)
        if tier_topic:
            _publish_event(tier_topic, index_complete_event)
            logger.info("Published index-complete to tier topic %s for scan %s", tier_topic, scan_id)
    except Exception:
        logger.exception("Failed to publish index-complete event for scan %s", scan_id)

    return IndexResponse(
        scan_id=scan_id,
        status="complete",
        total_files=len(file_paths),
        total_chunks=len(all_chunks),
        total_embedded=total_embedded,
        deep_analysis=deep_analysis,
    )


# ------------------------------------------------------------------ Kafka consumer

def _kafka_consumer_loop() -> None:
    """Background thread: consume index-events from Kafka."""
    consumer = Consumer({
        "bootstrap.servers": config.KAFKA_BOOTSTRAP,
        "group.id": "indexer-group",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })
    consumer.subscribe([config.TOPIC_INDEX])
    logger.info("Kafka consumer started, listening on %s", config.TOPIC_INDEX)

    loop = asyncio.new_event_loop()

    while not _shutdown_event.is_set():
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            logger.error("Kafka consumer error: %s", msg.error())
            continue

        try:
            payload = json.loads(msg.value().decode("utf-8"))
            request = IndexRequest(**payload)
            logger.info("Received index event for scan %s", request.scan_id)
            loop.run_until_complete(_run_indexing(request))
        except Exception:
            logger.exception("Failed to process Kafka index event")

    consumer.close()
    loop.close()
    logger.info("Kafka consumer stopped")


# ------------------------------------------------------------------ FastAPI app

@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_consumer_thread
    kafka_consumer_thread = threading.Thread(
        target=_kafka_consumer_loop, daemon=True, name="kafka-consumer"
    )
    kafka_consumer_thread.start()
    logger.info("Indexer service started")
    yield
    _shutdown_event.set()
    if kafka_consumer_thread and kafka_consumer_thread.is_alive():
        kafka_consumer_thread.join(timeout=5)
    await embedder.close()
    logger.info("Indexer service stopped")


app = FastAPI(
    title="ChaosGuard Indexer",
    description="Code indexing service with AST-aware chunking and embedding",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "indexer"}


@app.post("/index", response_model=IndexResponse)
async def index_repo(request: IndexRequest):
    """Trigger indexing of a cloned repository."""
    try:
        result = await _run_indexing(request)
        return result
    except Exception as exc:
        logger.exception("Indexing failed for scan %s", request.scan_id)
        raise HTTPException(status_code=500, detail=str(exc))
