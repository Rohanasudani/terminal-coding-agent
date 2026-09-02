from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from .models import AgentConfig, ApprovalMode


def load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    termagent = data.get("termagent", data)
    if not isinstance(termagent, dict):
        raise TypeError("termagent config must be a table")
    return termagent


def apply_config_file(config: AgentConfig, path: Path) -> AgentConfig:
    data = load_config_file(path)
    if not data:
        return config

    allowed = {
        "approval_mode",
        "max_steps",
        "provider",
        "model",
        "test_command",
        "provider_retries",
        "log_dir",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"unknown config key(s): {', '.join(unknown)}")

    updates: dict[str, object] = {}
    if "approval_mode" in data:
        updates["approval_mode"] = parse_approval_mode(data["approval_mode"])
    if "max_steps" in data:
        updates["max_steps"] = int(data["max_steps"])
    if "provider" in data:
        updates["provider"] = str(data["provider"])
    if "model" in data:
        updates["model"] = str(data["model"])
    if "test_command" in data:
        updates["test_command"] = str(data["test_command"])
    if "provider_retries" in data:
        updates["provider_retries"] = int(data["provider_retries"])
    if "log_dir" in data:
        updates["log_dir"] = Path(str(data["log_dir"]))

    return replace(config, **updates)


def parse_approval_mode(value: object) -> ApprovalMode:
    if value in {"never", "suggest", "auto"}:
        return value  # type: ignore[return-value]
    raise ValueError("approval_mode must be one of: never, suggest, auto")
