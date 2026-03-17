from __future__ import annotations

import logging
from chunker.base_chunker import BaseChunker, CodeChunk
from chunker.java_chunker import JavaChunker
from chunker.python_chunker import PythonChunker

logger = logging.getLogger(__name__)

# Lazily initialised singletons
_chunkers: dict[str, BaseChunker] = {}

EXTENSION_MAP: dict[str, str] = {
    ".java": "java",
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".yml": "yaml",
    ".yaml": "yaml",
}

LANGUAGE_CHUNKER_MAP: dict[str, type[BaseChunker]] = {
    "java": JavaChunker,
    "python": PythonChunker,
}


def _get_chunker(language: str) -> BaseChunker | None:
    """Return a cached chunker for the given language, or None if unsupported."""
    if language not in LANGUAGE_CHUNKER_MAP:
        return None
    if language not in _chunkers:
        _chunkers[language] = LANGUAGE_CHUNKER_MAP[language]()
    return _chunkers[language]


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    for ext, lang in EXTENSION_MAP.items():
        if file_path.endswith(ext):
            return lang
    return "unknown"


def chunk_file(source_code: str, file_path: str, scan_id: str) -> list[CodeChunk]:
    """Route a file to the appropriate chunker, falling back to a file-level chunk."""
    from chunker.safe_parser import safe_parse

    language = detect_language(file_path)
    chunker = _get_chunker(language)

    if chunker is not None:
        try:
            return safe_parse(chunker, source_code, file_path, scan_id)
        except Exception:
            logger.exception("Chunker failed for %s, falling back to file-level chunk", file_path)

    # Fallback: file-level chunk for unsupported / failed languages
    return [
        CodeChunk(
            scan_id=scan_id,
            file_path=file_path,
            language=language,
            chunk_type="file",
            name=file_path.split("/")[-1],
            content=source_code,
            start_line=1,
            end_line=source_code.count("\n") + 1,
            metadata={},
            parent_chunk_id=None,
        )
    ]
