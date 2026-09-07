from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from .models import AgentConfig, ApprovalMode, PromptProfile, ReasoningEffort


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
        "prompt_profile",
        "max_cost_usd",
        "max_validation_errors",
        "observation_limit",
        "max_observation_chars",
        "max_output_tokens",
        "reasoning_effort",
        "allow_network_commands",
        "require_changes",
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
    if "prompt_profile" in data:
        updates["prompt_profile"] = parse_prompt_profile(data["prompt_profile"])
    if "max_cost_usd" in data:
        updates["max_cost_usd"] = parse_optional_float(data["max_cost_usd"])
    if "max_validation_errors" in data:
        updates["max_validation_errors"] = int(data["max_validation_errors"])
    if "observation_limit" in data:
        updates["observation_limit"] = int(data["observation_limit"])
    if "max_observation_chars" in data:
        updates["max_observation_chars"] = int(data["max_observation_chars"])
    if "max_output_tokens" in data:
        updates["max_output_tokens"] = int(data["max_output_tokens"])
    if "reasoning_effort" in data:
        updates["reasoning_effort"] = parse_reasoning_effort(data["reasoning_effort"])
    if "allow_network_commands" in data:
        updates["allow_network_commands"] = bool(data["allow_network_commands"])
    if "require_changes" in data:
        updates["require_changes"] = bool(data["require_changes"])
    if "log_dir" in data:
        updates["log_dir"] = Path(str(data["log_dir"]))

    return replace(config, **updates)


def parse_approval_mode(value: object) -> ApprovalMode:
    if value in {"never", "suggest", "auto"}:
        return value  # type: ignore[return-value]
    raise ValueError("approval_mode must be one of: never, suggest, auto")


def parse_prompt_profile(value: object) -> PromptProfile:
    if value in {"conservative", "benchmark", "fast"}:
        return value  # type: ignore[return-value]
    raise ValueError("prompt_profile must be one of: conservative, benchmark, fast")


def parse_reasoning_effort(value: object) -> ReasoningEffort | None:
    if value is None or value == "none":
        return None
    if value in {"minimal", "low", "medium", "high"}:
        return value  # type: ignore[return-value]
    raise ValueError("reasoning_effort must be one of: none, minimal, low, medium, high")


def parse_optional_float(value: object) -> float | None:
    if value is None or value == "none":
        return None
    return float(value)
