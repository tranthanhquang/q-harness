from __future__ import annotations

from dataclasses import dataclass

import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser


@dataclass(frozen=True, slots=True)
class ParsedSymbol:
    name: str
    kind: str
    line: int


_PYTHON = Language(tree_sitter_python.language())
_TYPESCRIPT = Language(tree_sitter_typescript.language_typescript())
_KINDS = {
    "class_definition": "class",
    "function_definition": "function",
    "class_declaration": "class",
    "function_declaration": "function",
    "method_definition": "method",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
}


def _walk(node: Node, source: bytes, symbols: list[ParsedSymbol]) -> None:
    kind = _KINDS.get(node.type)
    if kind:
        name_node = node.child_by_field_name("name")
        if name_node:
            symbols.append(
                ParsedSymbol(
                    source[name_node.start_byte : name_node.end_byte].decode("utf-8"),
                    kind,
                    node.start_point.row + 1,
                )
            )
    for child in node.children:
        _walk(child, source, symbols)


def extract_symbols(path: str, content: str) -> list[ParsedSymbol]:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    language = (
        _PYTHON if suffix == "py" else _TYPESCRIPT if suffix in {"ts", "tsx", "js", "jsx"} else None
    )
    if language is None:
        return []
    source = content.encode("utf-8")
    tree = Parser(language).parse(source)
    symbols: list[ParsedSymbol] = []
    _walk(tree.root_node, source, symbols)
    return symbols
