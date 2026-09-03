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


def test_build_code_map_indexes_typescript_and_javascript(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "math.ts").write_text(
        """
import { round } from "./rounding";

export function priceWithTax(total: number, rate: number) {
    return round(total * (1 + rate));
}

export const formatPrice = (value: number) => `$${value}`;
""",
        encoding="utf-8",
    )
    (src / "widget.jsx").write_text(
        """
import React from "react";

export class PriceTag extends React.Component {
    render() {
        return null;
    }
}
""",
        encoding="utf-8",
    )

    code_map = build_code_map(tmp_path)

    assert ("priceWithTax", "function", "src/math.ts", "typescript") in {
        (symbol.name, symbol.kind, symbol.path, symbol.language) for symbol in code_map.symbols
    }
    assert ("formatPrice", "function", "src/math.ts", "typescript") in {
        (symbol.name, symbol.kind, symbol.path, symbol.language) for symbol in code_map.symbols
    }
    assert ("PriceTag", "class", "src/widget.jsx", "javascript-react") in {
        (symbol.name, symbol.kind, symbol.path, symbol.language) for symbol in code_map.symbols
    }
    assert ("src/math.ts", "./rounding", "typescript") in {
        (edge.importer, edge.imported, edge.language) for edge in code_map.imports
    }
    assert ("src/widget.jsx", "react", "javascript-react") in {
        (edge.importer, edge.imported, edge.language) for edge in code_map.imports
    }
    assert ("round", "src/math.ts", "typescript") in {
        (reference.name, reference.path, reference.language) for reference in code_map.references
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
