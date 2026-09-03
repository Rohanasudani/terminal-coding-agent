from pathlib import Path

from termagent.code_map import (
    build_code_map,
    format_code_map,
    format_references,
    validate_python_source,
)


def test_build_code_map_extracts_symbols_imports_and_references(tmp_path: Path):
    (tmp_path / "service.py").write_text(
        """
import os
from helpers import normalize


class UserService:
    def create_user(self, email):
        return normalize(email)
""",
        encoding="utf-8",
    )

    code_map = build_code_map(tmp_path)

    assert ("UserService", "class", "service.py", 6) in {
        (symbol.name, symbol.kind, symbol.path, symbol.line) for symbol in code_map.symbols
    }
    assert ("create_user", "function", "service.py", 7) in {
        (symbol.name, symbol.kind, symbol.path, symbol.line) for symbol in code_map.symbols
    }
    assert ("service.py", "helpers.normalize") in {
        (edge.importer, edge.imported) for edge in code_map.imports
    }
    assert ("normalize", "service.py") in {
        (reference.name, reference.path) for reference in code_map.references
    }


def test_format_code_map_filters_by_query(tmp_path: Path):
    (tmp_path / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("def beta():\n    return 2\n", encoding="utf-8")

    output = format_code_map(build_code_map(tmp_path), query="alpha")

    assert "function alpha at alpha.py:1" in output
    assert "function beta" not in output


def test_format_references_reports_symbol_usage(tmp_path: Path):
    (tmp_path / "module.py").write_text(
        "def normalize(value):\n    return value\n\nresult = normalize('x')\n",
        encoding="utf-8",
    )

    output = format_references(build_code_map(tmp_path), "normalize")

    assert "module.py:4" in output
    assert "reference to normalize" in output


def test_validate_python_source_reports_syntax_errors():
    error = validate_python_source("broken.py", "def broken(:\n    pass\n")

    assert error is not None
    assert "broken.py" in error
