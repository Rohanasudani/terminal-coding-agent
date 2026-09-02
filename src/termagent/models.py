from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ApprovalMode = Literal["never", "suggest", "auto"]
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


@dataclass
class AgentState:
    steps: int = 0
    final_answer: str | None = None
    completed: bool = False
    tests_passed: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
