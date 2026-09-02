from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .agent import TerminalAgent
from .bench import run_benchmark, write_markdown_report, write_report
from .config import apply_config_file
from .models import AgentConfig
from .tools import ToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="termagent", description="Benchmarkable terminal coding agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run the agent against a repository task")
    run.add_argument("--repo", required=True, type=Path)
    run.add_argument("--task", required=True)
    run.add_argument("--config", type=Path)
    run.add_argument("--provider", choices=["mock", "repair", "openai"])
    run.add_argument("--model")
    run.add_argument("--approval-mode", choices=["never", "suggest", "auto"])
    run.add_argument("--max-steps", type=int)
    run.add_argument("--log-dir", type=Path)
    run.add_argument("--test-command")
    run.add_argument("--provider-retries", type=int)
    run.add_argument("--prompt-profile", choices=["conservative", "benchmark", "fast"])
    run.add_argument("--max-cost-usd", type=float)
    run.add_argument("--max-validation-errors", type=int)
    run.add_argument("--observation-limit", type=int)
    run.add_argument("--max-observation-chars", type=int)
    run.add_argument("--allow-network-commands", action="store_true")

    tools = subparsers.add_parser("tools", help="List available tools")
    tools.add_argument("--repo", type=Path, default=Path("."))

    bench = subparsers.add_parser("bench", help="Run local benchmark tasks")
    bench.add_argument("--repo-root", type=Path, default=Path("."))
    bench.add_argument("--tasks-dir", type=Path)
    bench.add_argument("--report", type=Path, default=Path("bench/results/latest.json"))
    bench.add_argument("--markdown-report", type=Path, default=Path("bench/results/latest.md"))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "tools":
        registry = ToolRegistry(args.repo, "suggest")
        print(json.dumps([spec.__dict__ for spec in registry.specs()], indent=2))
        return 0

    if args.command == "run":
        config_path = args.config or args.repo / "termagent.toml"
        config = apply_config_file(
            AgentConfig(
                repo=args.repo,
                task=args.task,
                log_dir=Path(".termagent/traces"),
            ),
            config_path,
        )
        overrides = {
            key: value
            for key, value in {
                "provider": args.provider,
                "model": args.model,
                "approval_mode": args.approval_mode,
                "max_steps": args.max_steps,
                "log_dir": args.log_dir,
                "test_command": args.test_command,
                "provider_retries": args.provider_retries,
                "prompt_profile": args.prompt_profile,
                "max_cost_usd": args.max_cost_usd,
                "max_validation_errors": args.max_validation_errors,
                "observation_limit": args.observation_limit,
                "max_observation_chars": args.max_observation_chars,
                "allow_network_commands": True if args.allow_network_commands else None,
            }.items()
            if value is not None
        }
        config = replace(
            config,
            repo=args.repo,
            task=args.task,
            **overrides,
        )
        state = TerminalAgent(config).run()
        print(state.final_answer)
        return 0 if state.completed else 1

    if args.command == "bench":
        results = run_benchmark(args.repo_root, args.tasks_dir)
        write_report(results, args.report)
        write_markdown_report(results, args.markdown_report)
        passed = sum(1 for result in results if result.passed)
        print(f"{passed}/{len(results)} tasks passed")
        print(args.report)
        print(args.markdown_report)
        return 0 if passed == len(results) else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
