from __future__ import annotations

import re


def first_search_path(output: str) -> str | None:
    for line in output.splitlines():
        if ":" not in line:
            continue
        path = line.split(":", 1)[0].strip()
        if path.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
            return path
    return None


def first_code_map_symbol_path(output: str) -> str | None:
    match = re.search(r"-\s+[\w-]+\s+\w+\s+\w+\s+at\s+([^:\n]+\.(?:py|js|jsx|ts|tsx)):\d+", output)
    return match.group(1) if match else None
