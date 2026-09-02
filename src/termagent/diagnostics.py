from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TestFailure:
    file_path: str | None
    symbol: str | None
    assertion: str | None
    raw: str


PYTHON_FILE_RE = re.compile(r"(?P<path>[\w./-]+\.py):\d+")
WHERE_CALL_RE = re.compile(r"where\s+.*?=\s+(?P<symbol>[A-Za-z_]\w*)\(")
ASSERTION_RE = re.compile(r"E\s+assert\s+(?P<assertion>.+)")


def parse_pytest_failure(output: str) -> TestFailure:
    file_match = PYTHON_FILE_RE.search(output)
    symbol_match = WHERE_CALL_RE.search(output)
    assertion_match = ASSERTION_RE.search(output)

    return TestFailure(
        file_path=file_match.group("path") if file_match else None,
        symbol=symbol_match.group("symbol") if symbol_match else None,
        assertion=assertion_match.group("assertion").strip() if assertion_match else None,
        raw=output,
    )


def tests_passed(output: str) -> bool:
    lowered = output.lower()
    failed = re.search(r"\b\d+\s+failed\b", lowered)
    errors = re.search(r"\b\d+\s+errors?\b", lowered)
    passed = re.search(r"\b\d+\s+passed\b", lowered)

    return bool(passed) and not failed and not errors
