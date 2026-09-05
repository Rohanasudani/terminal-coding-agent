from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .agent import TerminalAgent
from .bench import run_benchmark, write_markdown_report, write_report
from .config import apply_config_file
from .harbor import (
    compare_benchmark_reports,
    export_harbor_dataset,
    write_comparison_markdown,
    write_harbor_export_manifest,
)
from .health import (
    format_health_checks,
    health_checks_as_dicts,
    health_checks_passed,
    run_health_checks,
)
from .interactive import InteractiveSettings, run_interactive_app
from .live_smoke import live_smoke_result_as_dict, run_live_smoke
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

    harbor_export = subparsers.add_parser("harbor-export", help="Export local tasks to a Harbor-shaped dataset")
    harbor_export.add_argument("--tasks-dir", type=Path, default=Path("bench/tasks"))
    harbor_export.add_argument("--output-dir", type=Path, default=Path("bench/harbor-export"))
    harbor_export.add_argument("--manifest", type=Path, default=Path("bench/harbor-export/manifest.json"))
    harbor_export.add_argument("--limit", type=int)
    harbor_export.add_argument("--task-id", action="append", dest="task_ids")
    harbor_export.add_argument("--overwrite", action="store_true")

    compare = subparsers.add_parser("compare-bench", help="Compare benchmark JSON reports")
    compare.add_argument("reports", nargs="+", type=Path)
    compare.add_argument("--label", action="append", dest="labels")
    compare.add_argument("--markdown-report", type=Path, default=Path("bench/results/comparison.md"))

    doctor = subparsers.add_parser("doctor", help="Check local TermAgent prerequisites")
    doctor.add_argument("--repo", type=Path, default=Path("."))
    doctor.add_argument("--json", action="store_true", dest="json_output")

    app = subparsers.add_parser("app", help="Start interactive terminal agent mode")
    app.add_argument("--repo", type=Path, default=Path("."))
    app.add_argument("--provider", choices=["mock", "repair", "openai"], default="repair")
    app.add_argument("--model", default="gpt-5.6-luna")
    app.add_argument("--approval-mode", choices=["never", "suggest", "auto"], default="suggest")
    app.add_argument("--max-steps", type=int, default=12)
    app.add_argument("--test-command", default="{python} -m pytest -q")
    app.add_argument("--log-dir", type=Path, default=Path(".termagent/app-traces"))
    app.add_argument("--prompt-profile", choices=["conservative", "benchmark", "fast"], default="conservative")
    app.add_argument("--max-cost-usd", type=float, default=0.25)
    app.add_argument("--allow-network-commands", action="store_true")

    live_smoke = subparsers.add_parser("live-smoke", help="Run a tiny capped OpenAI provider smoke test")
    live_smoke.add_argument("--repo-root", type=Path, default=Path("."))
    live_smoke.add_argument("--model", default="gpt-5.6-luna")
    live_smoke.add_argument("--max-cost-usd", type=float, default=0.05)
    live_smoke.add_argument("--report", type=Path, default=Path("docs/live-provider-demo.md"))
    live_smoke.add_argument("--json", action="store_true", dest="json_output")

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

    if args.command == "harbor-export":
        exports = export_harbor_dataset(
            args.tasks_dir,
            args.output_dir,
            limit=args.limit,
            task_ids=set(args.task_ids) if args.task_ids else None,
            overwrite=args.overwrite,
        )
        write_harbor_export_manifest(exports, args.manifest)
        print(f"exported {len(exports)} tasks")
        print(args.output_dir)
        print(args.manifest)
        return 0

    if args.command == "compare-bench":
        comparisons = compare_benchmark_reports(args.reports, args.labels)
        write_comparison_markdown(comparisons, args.markdown_report)
        for comparison in comparisons:
            print(f"{comparison.label}: {comparison.passed}/{comparison.total} ({comparison.pass_rate:.1%})")
        print(args.markdown_report)
        return 0

    if args.command == "doctor":
        checks = run_health_checks(args.repo)
        if args.json_output:
            print(json.dumps(health_checks_as_dicts(checks), indent=2))
        else:
            print(format_health_checks(checks))
        return 0 if health_checks_passed(checks) else 1

    if args.command == "app":
        return run_interactive_app(
            InteractiveSettings(
                repo=args.repo,
                provider=args.provider,
                model=args.model,
                approval_mode=args.approval_mode,
                max_steps=args.max_steps,
                test_command=args.test_command,
                log_dir=args.log_dir,
                prompt_profile=args.prompt_profile,
                max_cost_usd=args.max_cost_usd,
                allow_network_commands=args.allow_network_commands,
            )
        )

    if args.command == "live-smoke":
        result = run_live_smoke(
            args.repo_root,
            model=args.model,
            max_cost_usd=args.max_cost_usd,
            report_path=args.report,
        )
        if args.json_output:
            print(json.dumps(live_smoke_result_as_dict(result), indent=2))
        else:
            print(f"live smoke {result.status}")
            print(result.report_path)
            print(result.note)
        return 0 if result.status in {"passed", "skipped"} else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
