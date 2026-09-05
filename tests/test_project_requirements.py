from pathlib import Path

from termagent.cli import build_parser
from termagent.tools import ToolRegistry

REQUIRED_COMMANDS = {
    "run",
    "app",
    "tools",
    "bench",
    "harbor-export",
    "compare-bench",
    "doctor",
    "live-smoke",
}

REQUIRED_TOOLS = {
    "search",
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
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/architecture.md",
    "docs/architecture-diagram.md",
    "docs/benchmark-report.md",
    "docs/benchmarking.md",
    "docs/demo.md",
    "docs/harbor-terminal-bench.md",
    "docs/interactive-app.md",
    "docs/live-provider-demo.md",
    "docs/project-brief.md",
    "docs/repository-intelligence.md",
    "docs/requirements-traceability.md",
    "docs/roadmap.md",
    "docs/security-audit.md",
]


def test_public_cli_exposes_required_commands():
    parser = build_parser()
    subparsers_action = next(action for action in parser._actions if action.dest == "command")

    assert REQUIRED_COMMANDS.issubset(subparsers_action.choices)


def test_tool_registry_exposes_project_requirements(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "suggest")

    assert REQUIRED_TOOLS == {spec.name for spec in tools.specs()}


def test_required_project_docs_exist():
    repo_root = Path(__file__).parents[1]

    missing = [path for path in REQUIRED_DOCS if not (repo_root / path).exists()]
    assert missing == []


def test_requirements_traceability_mentions_boundaries():
    repo_root = Path(__file__).parents[1]
    content = (repo_root / "docs" / "requirements-traceability.md").read_text(encoding="utf-8")

    assert "OpenAI live mode is implemented" in content
    assert "not a public Terminal-Bench leaderboard score" in content
    assert "not a complete operating-system sandbox" in content


def test_readme_and_security_audit_reference_latest_milestones():
    repo_root = Path(__file__).parents[1]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    security = (repo_root / "docs" / "security-audit.md").read_text(encoding="utf-8")

    assert "termagent app" in readme
    assert "requirements-traceability.md" in readme
    assert "14. Live-provider smoke readiness" in security
