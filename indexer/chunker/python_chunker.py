from __future__ import annotations

import logging
from tree_sitter import Language, Parser
import tree_sitter_python as ts_python

from chunker.base_chunker import BaseChunker, CodeChunk

logger = logging.getLogger(__name__)

PYTHON_LANGUAGE = Language(ts_python.language())


class PythonChunker(BaseChunker):
    """AST-aware Python code chunker using tree-sitter."""

    def __init__(self) -> None:
        self.parser = Parser(PYTHON_LANGUAGE)

    def chunk(self, source_code: str, file_path: str, scan_id: str) -> list[CodeChunk]:
        tree = self.parser.parse(source_code.encode("utf-8"))
        root = tree.root_node
        chunks: list[CodeChunk] = []

        # Extract imports as shared metadata
        imports = self._extract_imports(root, source_code)

        # Extract top-level classes and functions
        classes = self._find_direct_children(root, ["class_definition"])
        functions = self._find_direct_children(root, ["function_definition"])

        if not classes and not functions:
            # Fallback: file-level chunk
            chunk = CodeChunk(
                scan_id=scan_id,
                file_path=file_path,
                language="python",
                chunk_type="file",
                name=file_path.split("/")[-1],
                content=source_code,
                start_line=1,
                end_line=source_code.count("\n") + 1,
                metadata={"imports": imports},
                parent_chunk_id=None,
            )
            chunks.append(chunk)
            return chunks

        # Process classes
        for class_node in classes:
            name_node = class_node.child_by_field_name("name")
            class_name = self._node_text(name_node, source_code) if name_node else "Unknown"

            decorators = self._get_decorators(class_node, source_code)
            bases = self._get_bases(class_node, source_code)

            class_content = self._node_text(class_node, source_code)
            # Include decorators in content if present
            decorated_node = class_node.parent
            if decorated_node and decorated_node.type == "decorated_definition":
                class_content = self._node_text(decorated_node, source_code)
                start_line = decorated_node.start_point[0] + 1
                end_line = decorated_node.end_point[0] + 1
            else:
                start_line = class_node.start_point[0] + 1
                end_line = class_node.end_point[0] + 1

            class_chunk = CodeChunk(
                scan_id=scan_id,
                file_path=file_path,
                language="python",
                chunk_type="class",
                name=class_name,
                content=class_content,
                start_line=start_line,
                end_line=end_line,
                metadata={
                    "imports": imports,
                    "decorators": decorators,
                    "bases": bases,
                },
                parent_chunk_id=None,
            )
            chunks.append(class_chunk)

            # Extract methods within the class
            body_node = class_node.child_by_field_name("body")
            if body_node is None:
                continue

            method_nodes = self._find_direct_children(body_node, ["function_definition"])
            for method_node in method_nodes:
                method_name_node = method_node.child_by_field_name("name")
                method_name = self._node_text(method_name_node, source_code) if method_name_node else "Unknown"
                method_decorators = self._get_decorators(method_node, source_code)
                return_annotation = self._get_return_annotation(method_node, source_code)

                method_content = self._node_text(method_node, source_code)
                decorated_method = method_node.parent
                if decorated_method and decorated_method.type == "decorated_definition":
                    method_content = self._node_text(decorated_method, source_code)
                    m_start = decorated_method.start_point[0] + 1
                    m_end = decorated_method.end_point[0] + 1
                else:
                    m_start = method_node.start_point[0] + 1
                    m_end = method_node.end_point[0] + 1

                method_chunk = CodeChunk(
                    scan_id=scan_id,
                    file_path=file_path,
                    language="python",
                    chunk_type="method",
                    name=f"{class_name}.{method_name}",
                    content=method_content,
                    start_line=m_start,
                    end_line=m_end,
                    metadata={
                        "decorators": method_decorators,
                        "return_annotation": return_annotation,
                        "class_name": class_name,
                    },
                    parent_chunk_id=class_chunk.chunk_id,
                )
                chunks.append(method_chunk)

        # Process top-level functions
        for func_node in functions:
            name_node = func_node.child_by_field_name("name")
            func_name = self._node_text(name_node, source_code) if name_node else "Unknown"
            decorators = self._get_decorators(func_node, source_code)
            return_annotation = self._get_return_annotation(func_node, source_code)

            func_content = self._node_text(func_node, source_code)
            decorated_func = func_node.parent
            if decorated_func and decorated_func.type == "decorated_definition":
                func_content = self._node_text(decorated_func, source_code)
                f_start = decorated_func.start_point[0] + 1
                f_end = decorated_func.end_point[0] + 1
            else:
                f_start = func_node.start_point[0] + 1
                f_end = func_node.end_point[0] + 1

            func_chunk = CodeChunk(
                scan_id=scan_id,
                file_path=file_path,
                language="python",
                chunk_type="function",
                name=func_name,
                content=func_content,
                start_line=f_start,
                end_line=f_end,
                metadata={
                    "imports": imports,
                    "decorators": decorators,
                    "return_annotation": return_annotation,
                },
                parent_chunk_id=None,
            )
            chunks.append(func_chunk)

        return chunks

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _node_text(node, source: str) -> str:
        return source[node.start_byte:node.end_byte]

    @staticmethod
    def _find_direct_children(node, type_names: list[str]) -> list:
        """Find direct children of a node, also checking inside decorated_definition."""
        results: list = []
        for child in node.children:
            if child.type in type_names:
                results.append(child)
            elif child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in type_names:
                        results.append(sub)
        return results

    @staticmethod
    def _extract_imports(root, source: str) -> list[str]:
        imports: list[str] = []
        for child in root.children:
            if child.type in ("import_statement", "import_from_statement"):
                imports.append(PythonChunker._node_text(child, source).strip())
        return imports

    @staticmethod
    def _get_decorators(node, source: str) -> list[str]:
        decorators: list[str] = []
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    decorators.append(PythonChunker._node_text(child, source).strip())
        return decorators

    @staticmethod
    def _get_bases(node, source: str) -> list[str]:
        bases: list[str] = []
        superclasses = node.child_by_field_name("superclasses")
        if superclasses:
            # argument_list contains the base classes
            for child in superclasses.children:
                if child.is_named:
                    bases.append(PythonChunker._node_text(child, source).strip())
        return bases

    @staticmethod
    def _get_return_annotation(node, source: str) -> str:
        ret = node.child_by_field_name("return_type")
        if ret:
            return PythonChunker._node_text(ret, source).strip()
        return ""
