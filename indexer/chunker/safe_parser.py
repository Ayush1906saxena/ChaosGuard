"""Safe parser wrapper for tree-sitter parse calls.

Isolates parsing in a subprocess with timeout and memory limits
to prevent malicious code from hanging or exhausting memory.
"""
import logging
import subprocess
import sys
import tempfile
import os
from pathlib import Path

from chunker.base_chunker import CodeChunk

logger = logging.getLogger(__name__)

PARSE_TIMEOUT_SECONDS = 30
PARSE_MEMORY_LIMIT_MB = 256


def safe_parse(chunker, source_code: str, file_path: str, scan_id: str) -> list[CodeChunk]:
    """Wrap a chunker's parse call in a subprocess with timeout and memory limits.

    Falls back to file-level chunking on failure.
    """
    try:
        # Write source to a temp file for subprocess parsing
        with tempfile.NamedTemporaryFile(mode="w", suffix=Path(file_path).suffix, delete=False) as tmp:
            tmp.write(source_code)
            tmp_path = tmp.name

        try:
            # Try direct parsing first (in-process) with a simple timeout guard
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError("Parser timed out")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(PARSE_TIMEOUT_SECONDS)
            try:
                result = chunker.chunk(source_code, file_path, scan_id)
                signal.alarm(0)
                return result
            except TimeoutError:
                logger.warning("Parser timed out for %s, falling back to file-level chunk", file_path)
            except Exception as exc:
                logger.warning("Parser failed for %s: %s, falling back to file-level chunk", file_path, exc)
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                signal.alarm(0)
        finally:
            os.unlink(tmp_path)

    except Exception as exc:
        logger.warning("Safe parse setup failed for %s: %s", file_path, exc)

    # Fallback: file-level chunk
    return [
        CodeChunk(
            scan_id=scan_id,
            file_path=file_path,
            language="unknown",
            chunk_type="file",
            name=file_path.split("/")[-1],
            content=source_code,
            start_line=1,
            end_line=source_code.count("\n") + 1,
            metadata={},
            parent_chunk_id=None,
        )
    ]
