from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras
from tree_sitter import Language, Parser
import tree_sitter_java as ts_java
import tree_sitter_python as ts_python

from config import config
from chunker.base_chunker import CodeChunk

logger = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(ts_java.language())
PYTHON_LANGUAGE = Language(ts_python.language())

LANGUAGE_MAP = {
    "java": JAVA_LANGUAGE,
    "python": PYTHON_LANGUAGE,
}

# SQL for dependency_graph table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dependency_graph (
    id SERIAL PRIMARY KEY,
    scan_id TEXT NOT NULL,
    caller_name TEXT NOT NULL,
    caller_file TEXT NOT NULL,
    callee_name TEXT NOT NULL,
    callee_file TEXT,
    call_line INTEGER,
    language TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_depgraph_scan ON dependency_graph(scan_id);
CREATE INDEX IF NOT EXISTS idx_depgraph_caller ON dependency_graph(scan_id, caller_name);
CREATE INDEX IF NOT EXISTS idx_depgraph_callee ON dependency_graph(scan_id, callee_name);
"""


class CallGraphTracer:
    """Traces function calls across files using tree-sitter and stores the
    directed call graph in PostgreSQL."""

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}
        self._ensure_table()

    def _get_parser(self, language: str) -> Parser | None:
        if language not in LANGUAGE_MAP:
            return None
        if language not in self._parsers:
            self._parsers[language] = Parser(LANGUAGE_MAP[language])
        return self._parsers[language]

    def _get_conn(self):
        return psycopg2.connect(config.POSTGRES_DSN)

    def _ensure_table(self) -> None:
        try:
            conn = self._get_conn()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(CREATE_TABLE_SQL)
            conn.close()
        except Exception:
            logger.warning("Could not ensure dependency_graph table exists", exc_info=True)

    def build_call_graph(self, scan_id: str, chunks: list[CodeChunk]) -> int:
        """Analyse chunks, extract call edges, store in DB. Returns edge count."""
        # Build a name→file map for resolution
        defined_names: dict[str, str] = {}
        for chunk in chunks:
            if chunk.chunk_type in ("method", "function", "constructor"):
                defined_names[chunk.name] = chunk.file_path
                # Also store short name for resolution
                short = chunk.name.split(".")[-1]
                if short not in defined_names:
                    defined_names[short] = chunk.file_path

        edges: list[dict[str, Any]] = []

        for chunk in chunks:
            if chunk.chunk_type not in ("method", "function", "constructor"):
                continue

            parser = self._get_parser(chunk.language)
            if parser is None:
                continue

            tree = parser.parse(chunk.content.encode("utf-8"))
            call_nodes = self._find_calls(tree.root_node, chunk.language)

            for callee_name, line_offset in call_nodes:
                edges.append({
                    "scan_id": scan_id,
                    "caller_name": chunk.name,
                    "caller_file": chunk.file_path,
                    "callee_name": callee_name,
                    "callee_file": defined_names.get(callee_name, ""),
                    "call_line": chunk.start_line + line_offset,
                    "language": chunk.language,
                })

        if not edges:
            return 0

        # Bulk insert
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO dependency_graph
                            (scan_id, caller_name, caller_file, callee_name, callee_file, call_line, language)
                        VALUES %s
                        """,
                        [
                            (
                                e["scan_id"], e["caller_name"], e["caller_file"],
                                e["callee_name"], e["callee_file"],
                                e["call_line"], e["language"],
                            )
                            for e in edges
                        ],
                    )
            logger.info("Stored %d call graph edges for scan %s", len(edges), scan_id)
        finally:
            conn.close()

        return len(edges)

    def get_callers(self, scan_id: str, function_name: str) -> list[dict[str, Any]]:
        """Get all callers of a function."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT caller_name, caller_file, call_line, language
                    FROM dependency_graph
                    WHERE scan_id = %s AND callee_name = %s
                    ORDER BY caller_file, call_line
                    """,
                    (scan_id, function_name),
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_callees(self, scan_id: str, function_name: str) -> list[dict[str, Any]]:
        """Get all functions called by a function."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT callee_name, callee_file, call_line, language
                    FROM dependency_graph
                    WHERE scan_id = %s AND caller_name = %s
                    ORDER BY call_line
                    """,
                    (scan_id, function_name),
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _find_calls(self, node, language: str) -> list[tuple[str, int]]:
        """Recursively find function/method call nodes, return (callee_name, line_offset)."""
        calls: list[tuple[str, int]] = []

        if language == "java":
            call_types = ("method_invocation",)
        elif language == "python":
            call_types = ("call",)
        else:
            call_types = ()

        if node.type in call_types:
            name = self._extract_call_name(node, language)
            if name:
                calls.append((name, node.start_point[0]))

        for child in node.children:
            calls.extend(self._find_calls(child, language))

        return calls

    @staticmethod
    def _extract_call_name(node, language: str) -> str:
        """Extract the callee name from a call node."""
        if language == "java":
            # method_invocation: object.method(args) or method(args)
            name_node = node.child_by_field_name("name")
            obj_node = node.child_by_field_name("object")
            if name_node:
                name = node.text.decode("utf-8") if node.text else ""
                # Simplify: just use the method name part
                name_text = name_node.text.decode("utf-8") if name_node.text else ""
                if obj_node:
                    obj_text = obj_node.text.decode("utf-8") if obj_node.text else ""
                    return f"{obj_text}.{name_text}"
                return name_text
        elif language == "python":
            func_node = node.child_by_field_name("function")
            if func_node:
                return func_node.text.decode("utf-8") if func_node.text else ""
        return ""
