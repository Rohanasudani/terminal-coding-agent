from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".termagent"}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    path: str
    line: int
    parent: str | None = None


@dataclass(frozen=True)
class ImportEdge:
    importer: str
    imported: str
    line: int


@dataclass(frozen=True)
class Reference:
    name: str
    path: str
    line: int
    kind: str


@dataclass(frozen=True)
class CodeMap:
    symbols: list[Symbol]
    imports: list[ImportEdge]
    references: list[Reference]
    parse_errors: dict[str, str]


def build_code_map(repo: Path) -> CodeMap:
    symbols: list[Symbol] = []
    imports: list[ImportEdge] = []
    references: list[Reference] = []
    parse_errors: dict[str, str] = {}

    for path in iter_python_files(repo):
        relative_path = os.fspath(path.relative_to(repo))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors[relative_path] = str(exc)
            continue

        visitor = CodeMapVisitor(relative_path)
        visitor.visit(tree)
        symbols.extend(visitor.symbols)
        imports.extend(visitor.imports)
        references.extend(visitor.references)

    return CodeMap(
        symbols=sorted(symbols, key=lambda item: (item.path, item.line, item.name)),
        imports=sorted(imports, key=lambda item: (item.importer, item.line, item.imported)),
        references=sorted(references, key=lambda item: (item.path, item.line, item.name)),
        parse_errors=parse_errors,
    )


def iter_python_files(repo: Path):
    for path in sorted(repo.rglob("*.py")):
        if IGNORED_DIRS.intersection(path.relative_to(repo).parts):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        yield path


class CodeMapVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.parents: list[str] = []
        self.symbols: list[Symbol] = []
        self.imports: list[ImportEdge] = []
        self.references: list[Reference] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node.name, "class", node.lineno)
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol(node.name, "function", node.lineno)
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_symbol(node.name, "async_function", node.lineno)
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(ImportEdge(self.path, alias.name, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            self.imports.append(ImportEdge(self.path, f"{module}.{alias.name}".strip("."), node.lineno))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.references.append(Reference(node.id, self.path, node.lineno, type(node.ctx).__name__.lower()))

    def _add_symbol(self, name: str, kind: str, line: int) -> None:
        parent = ".".join(self.parents) if self.parents else None
        self.symbols.append(Symbol(name=name, kind=kind, path=self.path, line=line, parent=parent))


def format_code_map(code_map: CodeMap, query: str | None = None, limit: int = 80) -> str:
    lowered_query = query.lower() if query else None
    symbols = [
        symbol
        for symbol in code_map.symbols
        if lowered_query is None or lowered_query in symbol.name.lower() or lowered_query in symbol.path.lower()
    ]
    imports = [
        edge
        for edge in code_map.imports
        if lowered_query is None
        or lowered_query in edge.imported.lower()
        or lowered_query in edge.importer.lower()
    ]

    lines = ["Symbols:"]
    for symbol in symbols[:limit]:
        parent = f" parent={symbol.parent}" if symbol.parent else ""
        lines.append(f"- {symbol.kind} {symbol.name} at {symbol.path}:{symbol.line}{parent}")

    if not symbols:
        lines.append("- no symbols matched")

    lines.append("")
    lines.append("Imports:")
    for edge in imports[:limit]:
        lines.append(f"- {edge.importer}:{edge.line} imports {edge.imported}")

    if not imports:
        lines.append("- no imports matched")

    if code_map.parse_errors:
        lines.append("")
        lines.append("Parse errors:")
        for path, error in sorted(code_map.parse_errors.items()):
            lines.append(f"- {path}: {error}")

    return "\n".join(lines)


def format_references(code_map: CodeMap, symbol: str, limit: int = 120) -> str:
    matches = [reference for reference in code_map.references if reference.name == symbol]
    if not matches:
        return f"no references found for {symbol}"

    return "\n".join(
        f"{reference.path}:{reference.line}: {reference.kind} reference to {reference.name}"
        for reference in matches[:limit]
    )


def validate_python_source(path: str, content: str) -> str | None:
    if not path.endswith(".py"):
        return None
    try:
        ast.parse(content, filename=path)
    except SyntaxError as exc:
        return f"{path}:{exc.lineno}:{exc.offset}: {exc.msg}"
    return None
