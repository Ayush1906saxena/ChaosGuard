from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_java as ts_java
import tree_sitter_python as ts_python

from chunker.base_chunker import CodeChunk

logger = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(ts_java.language())
PYTHON_LANGUAGE = Language(ts_python.language())

LANGUAGE_MAP = {
    "java": JAVA_LANGUAGE,
    "python": PYTHON_LANGUAGE,
}

# ----- Source and Sink Patterns -----

# Sources: untrusted data entry points
SOURCE_PATTERNS: dict[str, list[str]] = {
    "java": [
        "getParameter",
        "getHeader",
        "getCookies",
        "getInputStream",
        "getReader",
        "getPart",
        "getParts",
        "getQueryString",
        "getRequestURI",
        "getPathInfo",
        "getRemoteUser",
        "getAttribute",
        "getSession",
        "readLine",
        "readObject",
    ],
    "python": [
        "request.args",
        "request.form",
        "request.data",
        "request.json",
        "request.files",
        "request.headers",
        "request.cookies",
        "request.values",
        "request.get_json",
        "request.query_params",
        "request.body",
        "request.path_params",
        "input(",
        "sys.stdin",
        "os.environ",
    ],
}

# Sinks: dangerous operations
SINK_PATTERNS: dict[str, list[str]] = {
    "java": [
        "executeQuery",
        "executeUpdate",
        "execute(",
        "prepareStatement",
        "createStatement",
        "Runtime.exec",
        "ProcessBuilder",
        "getRuntime().exec",
        "FileWriter",
        "FileOutputStream",
        "PrintWriter",
        "sendRedirect",
        "forward",
        "include(",
        "setAttribute",
        "setHeader",
        "addHeader",
        "getWriter().write",
        "println(",
        "Class.forName",
        "loadClass",
        "newInstance",
        "invoke(",
        "eval(",
    ],
    "python": [
        "execute(",
        "executemany(",
        "cursor.execute",
        "raw(",
        "os.system(",
        "os.popen(",
        "subprocess.run(",
        "subprocess.call(",
        "subprocess.Popen(",
        "os.exec",
        "eval(",
        "exec(",
        "open(",
        "os.remove(",
        "os.unlink(",
        "shutil.rmtree(",
        "render_template_string(",
        "send_file(",
        "redirect(",
        "make_response(",
        "Response(",
        "jsonify(",
        "pickle.loads(",
        "yaml.load(",
        "marshal.loads(",
    ],
}


@dataclass
class DataFlowNode:
    node_type: str  # "source" or "sink"
    pattern: str  # Which pattern matched
    file_path: str
    line: int
    function_name: str
    content_snippet: str


@dataclass
class TrustBoundary:
    name: str
    sources: list[DataFlowNode] = field(default_factory=list)
    sinks: list[DataFlowNode] = field(default_factory=list)
    flows: list[dict[str, Any]] = field(default_factory=list)


class DataFlowTracker:
    """Identifies sources and sinks of untrusted data and maps flows between them."""

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: str) -> Parser | None:
        if language not in LANGUAGE_MAP:
            return None
        if language not in self._parsers:
            self._parsers[language] = Parser(LANGUAGE_MAP[language])
        return self._parsers[language]

    def analyse(self, chunks: list[CodeChunk], call_graph_edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Run full data-flow analysis. Returns trust boundary mapping."""

        sources: list[DataFlowNode] = []
        sinks: list[DataFlowNode] = []

        for chunk in chunks:
            if chunk.chunk_type not in ("method", "function", "constructor"):
                continue

            lang = chunk.language
            if lang not in SOURCE_PATTERNS:
                continue

            chunk_sources = self._find_patterns(
                chunk, SOURCE_PATTERNS[lang], "source"
            )
            chunk_sinks = self._find_patterns(
                chunk, SINK_PATTERNS.get(lang, []), "sink"
            )
            sources.extend(chunk_sources)
            sinks.extend(chunk_sinks)

        # Build trust boundaries
        boundaries = self._build_trust_boundaries(sources, sinks, call_graph_edges)

        return {
            "total_sources": len(sources),
            "total_sinks": len(sinks),
            "sources": [self._node_to_dict(s) for s in sources],
            "sinks": [self._node_to_dict(s) for s in sinks],
            "trust_boundaries": [
                {
                    "name": b.name,
                    "source_count": len(b.sources),
                    "sink_count": len(b.sinks),
                    "flow_count": len(b.flows),
                    "flows": b.flows,
                }
                for b in boundaries
            ],
        }

    def _find_patterns(
        self, chunk: CodeChunk, patterns: list[str], node_type: str
    ) -> list[DataFlowNode]:
        """Scan chunk content for matching patterns."""
        results: list[DataFlowNode] = []
        lines = chunk.content.split("\n")

        for line_offset, line in enumerate(lines):
            stripped = line.strip()
            for pattern in patterns:
                if pattern in stripped:
                    results.append(
                        DataFlowNode(
                            node_type=node_type,
                            pattern=pattern,
                            file_path=chunk.file_path,
                            line=chunk.start_line + line_offset,
                            function_name=chunk.name,
                            content_snippet=stripped[:200],
                        )
                    )
                    break  # One match per line is enough

        return results

    def _build_trust_boundaries(
        self,
        sources: list[DataFlowNode],
        sinks: list[DataFlowNode],
        call_graph_edges: list[dict[str, Any]] | None,
    ) -> list[TrustBoundary]:
        """Group sources and sinks into trust boundaries and trace flows."""

        # Group by file as a simple boundary heuristic
        file_boundaries: dict[str, TrustBoundary] = {}

        for source in sources:
            key = source.file_path
            if key not in file_boundaries:
                file_boundaries[key] = TrustBoundary(name=f"boundary:{key}")
            file_boundaries[key].sources.append(source)

        for sink in sinks:
            key = sink.file_path
            if key not in file_boundaries:
                file_boundaries[key] = TrustBoundary(name=f"boundary:{key}")
            file_boundaries[key].sinks.append(sink)

        # Trace flows: source→sink within same function or via call graph
        callee_map: dict[str, list[str]] = {}
        if call_graph_edges:
            for edge in call_graph_edges:
                caller = edge.get("caller_name", "")
                callee = edge.get("callee_name", "")
                callee_map.setdefault(caller, []).append(callee)

        # Build source function → set for quick lookup
        source_funcs: dict[str, list[DataFlowNode]] = {}
        for s in sources:
            source_funcs.setdefault(s.function_name, []).append(s)

        sink_funcs: dict[str, list[DataFlowNode]] = {}
        for s in sinks:
            sink_funcs.setdefault(s.function_name, []).append(s)

        for boundary in file_boundaries.values():
            for source in boundary.sources:
                # Direct flow: source and sink in same function
                if source.function_name in sink_funcs:
                    for sink in sink_funcs[source.function_name]:
                        boundary.flows.append({
                            "source_pattern": source.pattern,
                            "source_line": source.line,
                            "sink_pattern": sink.pattern,
                            "sink_line": sink.line,
                            "flow_type": "direct",
                            "function": source.function_name,
                        })

                # Indirect flow via call graph
                callees = callee_map.get(source.function_name, [])
                for callee in callees:
                    if callee in sink_funcs:
                        for sink in sink_funcs[callee]:
                            boundary.flows.append({
                                "source_pattern": source.pattern,
                                "source_line": source.line,
                                "sink_pattern": sink.pattern,
                                "sink_line": sink.line,
                                "flow_type": "indirect",
                                "via_function": callee,
                                "from_function": source.function_name,
                            })

        return list(file_boundaries.values())

    @staticmethod
    def _node_to_dict(node: DataFlowNode) -> dict[str, Any]:
        return {
            "type": node.node_type,
            "pattern": node.pattern,
            "file_path": node.file_path,
            "line": node.line,
            "function_name": node.function_name,
            "snippet": node.content_snippet,
        }
