import os
from dataclasses import dataclass


@dataclass
class Config:
    # Infrastructure
    POSTGRES_DSN: str = os.getenv("POSTGRES_DSN",
        f"postgresql://{os.getenv('POSTGRES_USER', 'chaosguard')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'chaosguard_dev_2026')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'chaosguard')}")

    REDIS_URL: str = os.getenv("REDIS_URL",
        f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}")

    KAFKA_BOOTSTRAP: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    CHROMADB_HOST: str = os.getenv("CHROMADB_HOST", "localhost")
    CHROMADB_PORT: int = int(os.getenv("CHROMADB_PORT", "8000"))

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Models
    CODE_MODEL: str = os.getenv("OLLAMA_CODE_MODEL", "qwen2.5-coder:7b")
    REASONING_MODEL: str = os.getenv("OLLAMA_REASONING_MODEL", "llama3.1:8b")
    EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Limits
    EMBEDDING_BATCH_SIZE: int = 32
    MAX_CHUNK_TOKENS: int = 2048
    MAX_CONTEXT_CHUNKS: int = 10
    AGENT_MAX_ITERATIONS: int = 3
    OLLAMA_TIMEOUT_SECONDS: int = 120
    OLLAMA_MAX_RETRIES: int = 3

    # Kafka Topics
    TOPIC_CLONE: str = os.getenv("KAFKA_TOPIC_CLONE", "repo-clone-events")
    TOPIC_INDEX: str = os.getenv("KAFKA_TOPIC_INDEX", "index-events")
    TOPIC_INDEX_COMPLETE: str = os.getenv("KAFKA_TOPIC_INDEX_COMPLETE", "index-complete")
    TOPIC_SCAN_PROGRESS: str = os.getenv("KAFKA_TOPIC_SCAN_PROGRESS", "scan-progress")
    TOPIC_SCAN_COMPLETE: str = os.getenv("KAFKA_TOPIC_SCAN_COMPLETE", "scan-complete")
    TOPIC_RESULTS_READY: str = os.getenv("KAFKA_TOPIC_RESULTS_READY", "results-ready")

    # Tier-specific Kafka Topics
    TOPIC_SCAN_RECON: str = os.getenv("KAFKA_TOPIC_SCAN_RECON", "scan-recon-events")
    TOPIC_SCAN_HUNTER: str = os.getenv("KAFKA_TOPIC_SCAN_HUNTER", "scan-hunter-events")
    TOPIC_SCAN_SIEGE: str = os.getenv("KAFKA_TOPIC_SCAN_SIEGE", "scan-siege-events")


config = Config()
