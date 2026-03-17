import uuid
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class CodeChunk:
    scan_id: str
    file_path: str
    language: str
    chunk_type: str
    name: str
    content: str
    start_line: int
    end_line: int
    metadata: dict
    parent_chunk_id: str | None
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] | None = None
    is_taint_source: bool = False
    is_taint_sink: bool = False

    def to_embedding_text(self) -> str:
        meta_str = ", ".join(f"{k}: {v}" for k, v in self.metadata.items()
                            if k != "imports" and v)
        return (
            f"{self.language} {self.chunk_type} {self.name}\n"
            f"File: {self.file_path}\n"
            f"Metadata: {meta_str}\n"
            f"Code:\n{self.content}"
        )


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, source_code: str, file_path: str, scan_id: str) -> list[CodeChunk]:
        pass
