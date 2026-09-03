from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".termagent", "node_modules", "dist", "build"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx"}

JS_FUNCTION_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\("
)
JS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)\b")
JS_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)
JS_METHOD_RE = re.compile(r"^\s*(?:async\s+)?(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")
JS_IMPORT_FROM_RE = re.compile(r"^\s*import\s+.+?\s+from\s+['\"](?P<module>[^'\"]+)['\"]")
JS_SIDE_EFFECT_IMPORT_RE = re.compile(r"^\s*import\s+['\"](?P<module>[^'\"]+)['\"]")
JS_REQUIRE_RE = re.compile(r"require\(['\"](?P<module>[^'\"]+)['\"]\)")
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][\w$]*\b")
JAVASCRIPT_KEYWORDS = {
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "default",
    "do",
    "else",
    "export",
    "extends",
    "false",
    "finally",
    "for",
    "from",
    "function",
    "if",
    "import",
    "in",
    "let",
    "new",
    "null",
    "of",
    "return",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "typeof",
    "undefined",
    "var",
    "while",
}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    path: str
    line: int
    language: str
    parent: str | None = None


@dataclass(frozen=True)
class ImportEdge:
    importer: str
    imported: str
    line: int
    language: str


@dataclass(frozen=True)
class Reference:
    name: str
    path: str
    line: int
    kind: str
    language: str


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

    for path in iter_source_files(repo):
        relative_path = os.fspath(path.relative_to(repo))
        file_map = build_python_file_map(path, relative_path) if path.suffix == ".py" else build_javascript_file_map(path, relative_path)
        symbols.extend(file_map.symbols)
        imports.extend(file_map.imports)
        references.extend(file_map.references)
        parse_errors.update(file_map.parse_errors)

    return CodeMap(
        symbols=sorted(symbols, key=lambda item: (item.path, item.line, item.name)),
        imports=sorted(imports, key=lambda item: (item.importer, item.line, item.imported)),
        references=sorted(references, key=lambda item: (item.path, item.line, item.name)),
        parse_errors=dict(sorted(parse_errors.items())),
    )


def iter_source_files(repo: Path):
    for path in sorted(repo.rglob("*")):
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        if IGNORED_DIRS.intersection(path.relative_to(repo).parts):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        yield path


def iter_python_files(repo: Path):
    for path in iter_source_files(repo):
        if path.suffix == ".py":
            yield path


def build_python_file_map(path: Path, relative_path: str) -> CodeMap:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        return CodeMap([], [], [], {relative_path: str(exc)})

    visitor = PythonCodeMapVisitor(relative_path)
    visitor.visit(tree)
    return CodeMap(visitor.symbols, visitor.imports, visitor.references, {})


def build_javascript_file_map(path: Path, relative_path: str) -> CodeMap:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return CodeMap([], [], [], {relative_path: "file is not valid UTF-8"})

    symbols: list[Symbol] = []
    imports: list[ImportEdge] = []
    references: list[Reference] = []
    language = javascript_language_for_path(path)
    class_scopes: list[tuple[str, int]] = []

    for line_number, line in enumerate(lines, start=1):
        parent = class_scopes[-1][0] if class_scopes else None
        symbol = javascript_symbol_from_line(line, inside_class=bool(class_scopes))
        opened_class_scope = False
        if symbol:
            name, kind = symbol
            symbols.append(Symbol(name, kind, relative_path, line_number, language, parent if kind == "method" else None))
            if kind == "class":
                class_scopes.append((name, brace_delta(line)))
                opened_class_scope = True

        imported = javascript_import_from_line(line)
        if imported:
            imports.append(ImportEdge(relative_path, imported, line_number, language))

        for name in identifiers_from_javascript_line(line):
            references.append(Reference(name, relative_path, line_number, "name", language))

        if class_scopes and not opened_class_scope:
            class_name, depth = class_scopes[-1]
            next_depth = depth + brace_delta(line)
            if next_depth <= 0:
                class_scopes.pop()
            else:
                class_scopes[-1] = (class_name, next_depth)

    return CodeMap(symbols, imports, references, {})


def javascript_language_for_path(path: Path) -> str:
    return {
        ".js": "javascript",
        ".jsx": "javascript-react",
        ".ts": "typescript",
        ".tsx": "typescript-react",
    }[path.suffix]


def javascript_symbol_from_line(line: str, inside_class: bool) -> tuple[str, str] | None:
    for pattern, kind in ((JS_FUNCTION_RE, "function"), (JS_CLASS_RE, "class"), (JS_ARROW_RE, "function")):
        match = pattern.search(line)
        if match:
            return match.group("name"), kind

    if inside_class:
        method = JS_METHOD_RE.search(line)
        if method and method.group("name") not in {"if", "for", "while", "switch", "catch"}:
            return method.group("name"), "method"

    return None


def javascript_import_from_line(line: str) -> str | None:
    for pattern in (JS_IMPORT_FROM_RE, JS_SIDE_EFFECT_IMPORT_RE, JS_REQUIRE_RE):
        match = pattern.search(line)
        if match:
            return match.group("module")
    return None


def identifiers_from_javascript_line(line: str) -> list[str]:
    stripped = line.lstrip()
    if stripped.startswith(("//", "*")):
        return []
    return [name for name in IDENTIFIER_RE.findall(line) if name not in JAVASCRIPT_KEYWORDS]


def brace_delta(line: str) -> int:
    return line.count("{") - line.count("}")


class PythonCodeMapVisitor(ast.NodeVisitor):
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
            self.imports.append(ImportEdge(self.path, alias.name, node.lineno, "python"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            imported = f"{module}.{alias.name}".strip(".")
            self.imports.append(ImportEdge(self.path, imported, node.lineno, "python"))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.references.append(Reference(node.id, self.path, node.lineno, type(node.ctx).__name__.lower(), "python"))

    def _add_symbol(self, name: str, kind: str, line: int) -> None:
        parent = ".".join(self.parents) if self.parents else None
        self.symbols.append(Symbol(name, kind, self.path, line, "python", parent))


def format_code_map(code_map: CodeMap, query: str | None = None, limit: int = 80) -> str:
    normalized_query = query.lower() if query else None
    symbols = [
        symbol
        for symbol in code_map.symbols
        if not normalized_query
        or normalized_query in symbol.name.lower()
        or normalized_query in symbol.path.lower()
        or normalized_query in symbol.language.lower()
    ][:limit]
    imports = [
        edge
        for edge in code_map.imports
        if not normalized_query
        or normalized_query in edge.imported.lower()
        or normalized_query in edge.importer.lower()
        or normalized_query in edge.language.lower()
    ][:limit]

    lines = ["Symbols:"]
    if symbols:
        for symbol in symbols:
            parent = f" parent={symbol.parent}" if symbol.parent else ""
            lines.append(f"- {symbol.language} {symbol.kind} {symbol.name} at {symbol.path}:{symbol.line}{parent}")
    else:
        lines.append("- none")

    lines.append("Imports:")
    if imports:
        for edge in imports:
            lines.append(f"- {edge.language} {edge.importer}:{edge.line} imports {edge.imported}")
    else:
        lines.append("- none")

    if code_map.parse_errors:
        lines.append("Parse errors:")
        for path, error in code_map.parse_errors.items():
            lines.append(f"- {path}: {error}")

    return "\n".join(lines)


def format_references(code_map: CodeMap, symbol: str, limit: int = 120) -> str:
    matches = [reference for reference in code_map.references if reference.name == symbol][:limit]
    if not matches:
        return f"No references found for {symbol}"
    return "\n".join(
        f"{reference.path}:{reference.line}: {reference.language} {reference.kind} reference to {reference.name}"
        for reference in matches
    )


def validate_python_source(path: str, content: str) -> str | None:
    if not path.endswith(".py"):
        return None
    try:
        ast.parse(content, filename=path)
    except SyntaxError as exc:
        return f"{path}:{exc.lineno}:{exc.offset}: {exc.msg}"
    return None
