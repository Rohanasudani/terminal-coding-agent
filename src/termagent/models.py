from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ApprovalMode = Literal["never", "suggest", "auto"]
PromptProfile = Literal["conservative", "benchmark", "fast"]
ToolStatus = Literal["ok", "error", "blocked"]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    status: ToolStatus
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ProviderOutput:
    tool_call: ToolCall
    usage: TokenUsage = field(default_factory=TokenUsage)
    attempts: int = 1


@dataclass(frozen=True)
class AgentConfig:
    repo: Path
    task: str
    approval_mode: ApprovalMode = "suggest"
    max_steps: int = 12
    log_dir: Path | None = None
    provider: str = "repair"
    model: str = "gpt-5.6-luna"
    test_command: str = "{python} -m pytest -q"
    provider_retries: int = 2
    prompt_profile: PromptProfile = "conservative"
    max_cost_usd: float | None = 0.25
    max_validation_errors: int = 2
    observation_limit: int = 6
    max_observation_chars: int = 8_000
    allow_network_commands: bool = False


@dataclass
class AgentState:
    steps: int = 0
    final_answer: str | None = None
    completed: bool = False
    tests_passed: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    changed_files: list[str] = field(default_factory=list)
    test_runs: list[str] = field(default_factory=list)
    failed_test_runs: int = 0
    patch_plans: int = 0
    validation_errors: int = 0
    stopped_by_cost_limit: bool = False
