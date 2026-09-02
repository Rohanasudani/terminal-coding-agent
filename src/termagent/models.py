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
class AgentConfig:
    repo: Path
    task: str
    approval_mode: ApprovalMode = "suggest"
    max_steps: int = 12
    log_dir: Path | None = None
    provider: str = "mock"


@dataclass
class AgentState:
    steps: int = 0
    final_answer: str | None = None
    completed: bool = False

