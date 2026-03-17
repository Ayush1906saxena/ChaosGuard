from __future__ import annotations

import logging
from tree_sitter import Language, Parser
import tree_sitter_java as ts_java

from chunker.base_chunker import BaseChunker, CodeChunk

logger = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(ts_java.language())


class JavaChunker(BaseChunker):
    """AST-aware Java code chunker using tree-sitter."""

    def __init__(self) -> None:
        self.parser = Parser(JAVA_LANGUAGE)

    def chunk(self, source_code: str, file_path: str, scan_id: str) -> list[CodeChunk]:
        tree = self.parser.parse(source_code.encode("utf-8"))
        root = tree.root_node
        chunks: list[CodeChunk] = []

        # Extract imports as shared metadata
        imports = self._extract_imports(root, source_code)
        package = self._extract_package(root, source_code)

        # Extract classes, interfaces, enums
        type_declarations = self._find_nodes(root, [
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
        ])

        if not type_declarations:
            # Fallback: file-level chunk
            chunk = CodeChunk(
                scan_id=scan_id,
                file_path=file_path,
                language="java",
                chunk_type="file",
                name=file_path.split("/")[-1],
                content=source_code,
                start_line=1,
                end_line=source_code.count("\n") + 1,
                metadata={"imports": imports, "package": package},
                parent_chunk_id=None,
            )
            chunks.append(chunk)
            return chunks

        for type_node in type_declarations:
            chunk_type = type_node.type.replace("_declaration", "")
            name_node = type_node.child_by_field_name("name")
            class_name = self._node_text(name_node, source_code) if name_node else "Unknown"

            annotations = self._get_annotations(type_node, source_code)
            superclass = self._get_superclass(type_node, source_code)
            interfaces = self._get_interfaces(type_node, source_code)
            access_modifier = self._get_access_modifier(type_node, source_code)

            class_content = self._node_text(type_node, source_code)
            class_chunk = CodeChunk(
                scan_id=scan_id,
                file_path=file_path,
                language="java",
                chunk_type=chunk_type,
                name=class_name,
                content=class_content,
                start_line=type_node.start_point[0] + 1,
                end_line=type_node.end_point[0] + 1,
                metadata={
                    "imports": imports,
                    "package": package,
                    "annotations": annotations,
                    "superclass": superclass,
                    "interfaces": interfaces,
                    "access_modifier": access_modifier,
                },
                parent_chunk_id=None,
            )
            chunks.append(class_chunk)

            # Extract methods within the class
            body_node = type_node.child_by_field_name("body")
            if body_node is None:
                continue

            method_nodes = self._find_nodes(body_node, [
                "method_declaration",
                "constructor_declaration",
            ])

            for method_node in method_nodes:
                method_name_node = method_node.child_by_field_name("name")
                method_name = self._node_text(method_name_node, source_code) if method_name_node else "Unknown"
                method_annotations = self._get_annotations(method_node, source_code)
                method_access = self._get_access_modifier(method_node, source_code)
                return_type = self._get_return_type(method_node, source_code)

                method_content = self._node_text(method_node, source_code)
                method_chunk = CodeChunk(
                    scan_id=scan_id,
                    file_path=file_path,
                    language="java",
                    chunk_type="method" if method_node.type == "method_declaration" else "constructor",
                    name=f"{class_name}.{method_name}",
                    content=method_content,
                    start_line=method_node.start_point[0] + 1,
                    end_line=method_node.end_point[0] + 1,
                    metadata={
                        "annotations": method_annotations,
                        "access_modifier": method_access,
                        "return_type": return_type,
                        "class_name": class_name,
                        "package": package,
                    },
                    parent_chunk_id=class_chunk.chunk_id,
                )
                chunks.append(method_chunk)

        return chunks

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _node_text(node, source: str) -> str:
        return source[node.start_byte:node.end_byte]

    @staticmethod
    def _find_nodes(node, type_names: list[str]) -> list:
        results: list = []
        if node.type in type_names:
            results.append(node)
        for child in node.children:
            results.extend(JavaChunker._find_nodes(child, type_names))
        return results

    @staticmethod
    def _extract_imports(root, source: str) -> list[str]:
        imports: list[str] = []
        for child in root.children:
            if child.type == "import_declaration":
                imports.append(JavaChunker._node_text(child, source).strip())
        return imports

    @staticmethod
    def _extract_package(root, source: str) -> str:
        for child in root.children:
            if child.type == "package_declaration":
                return JavaChunker._node_text(child, source).strip()
        return ""

    @staticmethod
    def _get_annotations(node, source: str) -> list[str]:
        annotations: list[str] = []
        # Annotations are sibling nodes before the declaration, or children of modifiers
        if node.parent is not None:
            idx = None
            for i, sibling in enumerate(node.parent.children):
                if sibling.id == node.id:
                    idx = i
                    break
            if idx is not None:
                for i in range(idx - 1, -1, -1):
                    sibling = node.parent.children[i]
                    if sibling.type in ("marker_annotation", "annotation"):
                        annotations.append(JavaChunker._node_text(sibling, source).strip())
                    else:
                        break

        # Also check inside modifiers child
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    if mod_child.type in ("marker_annotation", "annotation"):
                        annotations.append(JavaChunker._node_text(mod_child, source).strip())
        return annotations

    @staticmethod
    def _get_superclass(node, source: str) -> str:
        sc = node.child_by_field_name("superclass")
        if sc:
            return JavaChunker._node_text(sc, source).strip()
        return ""

    @staticmethod
    def _get_interfaces(node, source: str) -> list[str]:
        interfaces: list[str] = []
        ifaces = node.child_by_field_name("interfaces")
        if ifaces:
            for child in ifaces.children:
                if child.type == "type_list":
                    for type_node in child.children:
                        if type_node.is_named:
                            interfaces.append(JavaChunker._node_text(type_node, source).strip())
                elif child.is_named:
                    interfaces.append(JavaChunker._node_text(child, source).strip())
        return interfaces

    @staticmethod
    def _get_access_modifier(node, source: str) -> str:
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    if mod_child.type in ("public", "private", "protected"):
                        return mod_child.type
            if child.type in ("public", "private", "protected"):
                return child.type
        return "package-private"

    @staticmethod
    def _get_return_type(node, source: str) -> str:
        type_node = node.child_by_field_name("type")
        if type_node:
            return JavaChunker._node_text(type_node, source).strip()
        return "void"
