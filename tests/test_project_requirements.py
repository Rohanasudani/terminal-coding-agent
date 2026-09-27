import tomllib
from pathlib import Path

import pytest

from termagent import __version__
from termagent.cli import build_parser
from termagent.tools import ToolRegistry

REQUIRED_COMMANDS = {
    "run",
    "app",
    "tools",
    "bench",
    "harbor-export",
    "campaign-verify",
    "campaign-report",
    "compare-bench",
    "doctor",
    "live-smoke",
}

REQUIRED_TOOLS = {
    "set_task_plan",
    "submit_completion_review",
    "search",
    "list_files",
    "read_file",
    "code_map",
    "find_references",
    "plan_patch",
    "plan_patch_set",
    "write_file",
    "write_patch_set",
    "run_shell",
    "git_diff",
}

REQUIRED_DOCS = [
    "README.md",
    "DESIGN.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "docs/architecture.md",
    "docs/benchmarking.md",
    "docs/experiment-log.md",
    "docs/security.md",
]


def test_public_cli_exposes_required_commands():
    parser = build_parser()
    subparsers_action = next(action for action in parser._actions if action.dest == "command")

    assert REQUIRED_COMMANDS.issubset(subparsers_action.choices)


def test_interactive_cli_defaults_to_live_provider():
    args = build_parser().parse_args(["app"])

    assert args.provider == "openai"


def test_cli_and_package_metadata_expose_the_same_version(capsys):
    repo_root = Path(__file__).parents[1]
    metadata = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"termagent {__version__}"
    assert metadata["project"]["version"] == __version__


def test_tool_registry_exposes_project_requirements(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "suggest")

    assert REQUIRED_TOOLS == {spec.name for spec in tools.specs()}


def test_required_project_docs_exist():
    repo_root = Path(__file__).parents[1]

    missing = [path for path in REQUIRED_DOCS if not (repo_root / path).exists()]
    assert missing == []


def test_experiment_log_mentions_boundaries():
    repo_root = Path(__file__).parents[1]
    content = (repo_root / "docs" / "experiment-log.md").read_text(encoding="utf-8")

    assert "not a Terminal-Bench leaderboard score" in content
    assert "Every failed or errored trial remains in the denominator" in content


def test_readme_and_security_docs_reference_current_boundaries():
    repo_root = Path(__file__).parents[1]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    security = (repo_root / "docs" / "security.md").read_text(encoding="utf-8")

    assert "termagent app" in readme
    assert "experiment-log.md" in readme
    assert "not an operating-system sandbox" in security


def test_design_covers_runtime_decisions():
    repo_root = Path(__file__).parents[1]
    content = (repo_root / "DESIGN.md").read_text(encoding="utf-8")

    assert "## Problem" in content
    assert "## Design Principles" in content
    assert "## Evaluation Policy" in content
    assert "## Current Tradeoffs" in content
