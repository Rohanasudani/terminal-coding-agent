from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TraceLogger:
    def __init__(self, log_dir: Path | None) -> None:
        self.path: Path | None = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            self.path = log_dir / f"trace-{stamp}.jsonl"

    def write(self, event: str, payload: dict[str, Any]) -> None:
        if not self.path:
            return

        record = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

