from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .agent import TerminalAgent
from .health import format_health_checks, run_health_checks
from .models import AgentConfig, ApprovalMode, PromptProfile


class TaskRunner(Protocol):
    def __call__(self, config: AgentConfig) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class InteractiveSettings:
    repo: Path
    provider: str = "repair"
    model: str = "gpt-5.6-luna"
    approval_mode: ApprovalMode = "suggest"
    max_steps: int = 12
    test_command: str = "{python} -m pytest -q"
    log_dir: Path = Path(".termagent/app-traces")
    prompt_profile: PromptProfile = "conservative"
    max_cost_usd: float | None = 0.25
    allow_network_commands: bool = False


def run_interactive_app(
    settings: InteractiveSettings,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    runner: TaskRunner | None = None,
) -> int:
    run_task = runner or run_agent_task
    output_fn(interactive_banner(settings))

    while True:
        try:
            raw_task = input_fn("termagent> ")
        except EOFError:
            output_fn("")
            return 0
        except KeyboardInterrupt:
            output_fn("\nInterrupted. Type :quit to exit.")
            continue

        task = raw_task.strip()
        if not task:
            continue
        if task in {":q", ":quit", "quit", "exit"}:
            output_fn("Session closed.")
            return 0
        if task == ":help":
            output_fn(help_text())
            continue
        if task == ":doctor":
            output_fn(format_health_checks(run_health_checks(settings.repo)))
            continue

        output_fn(f"Running task: {task}")
        output_fn(run_task(agent_config_for_task(settings, task)))


def run_agent_task(config: AgentConfig) -> str:
    state = TerminalAgent(config).run()
    return state.final_answer or "Agent stopped without a final answer."


def agent_config_for_task(settings: InteractiveSettings, task: str) -> AgentConfig:
    return AgentConfig(
        repo=settings.repo,
        task=task,
        approval_mode=settings.approval_mode,
        max_steps=settings.max_steps,
        log_dir=settings.log_dir,
        provider=settings.provider,
        model=settings.model,
        test_command=settings.test_command,
        prompt_profile=settings.prompt_profile,
        max_cost_usd=settings.max_cost_usd,
        allow_network_commands=settings.allow_network_commands,
    )


def interactive_banner(settings: InteractiveSettings) -> str:
    return "\n".join(
        [
            "TermAgent interactive mode",
            f"repo: {settings.repo.resolve()}",
            f"provider: {settings.provider}",
            f"approval: {settings.approval_mode}",
            "Type a coding task, :doctor, :help, or :quit.",
        ]
    )


def help_text() -> str:
    return (
        "Commands:\n"
        "  :doctor  Check local prerequisites\n"
        "  :help    Show this help\n"
        "  :quit    Exit interactive mode\n"
        "\n"
        "Example task:\n"
        "  Fix the failing tests and show the final diff"
    )
