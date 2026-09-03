from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: str
    detail: str


def run_health_checks(repo: Path) -> list[HealthCheck]:
    resolved_repo = repo.resolve()
    checks = [
        check_python_version(),
        check_repo_root(resolved_repo),
        check_command("git", required=True),
        check_command("rg", required=False),
        check_command("node", required=False),
        check_openai_key(),
    ]
    return checks


def health_checks_as_dicts(checks: list[HealthCheck]) -> list[dict[str, str]]:
    return [asdict(check) for check in checks]


def format_health_checks(checks: list[HealthCheck]) -> str:
    width = max(len(check.name) for check in checks) if checks else 0
    return "\n".join(f"{check.status.upper():<7} {check.name:<{width}}  {check.detail}" for check in checks)


def health_checks_passed(checks: list[HealthCheck]) -> bool:
    return all(check.status != "fail" for check in checks)


def check_python_version() -> HealthCheck:
    version = sys.version_info
    if version >= (3, 11):
        return HealthCheck("python", "pass", f"{version.major}.{version.minor}.{version.micro}")
    return HealthCheck("python", "fail", "Python 3.11 or newer is required")


def check_repo_root(repo: Path) -> HealthCheck:
    if not repo.exists():
        return HealthCheck("repo", "fail", f"{repo} does not exist")
    if (repo / ".git").exists():
        return HealthCheck("repo", "pass", f"{repo} is a git repository")
    return HealthCheck("repo", "warn", f"{repo} exists but is not a git repository")


def check_command(command: str, *, required: bool) -> HealthCheck:
    path = shutil.which(command)
    if not path:
        status = "fail" if required else "warn"
        requirement = "required" if required else "optional"
        return HealthCheck(command, status, f"{requirement} command not found")

    version = command_version(command)
    detail = f"{path}" + (f" ({version})" if version else "")
    return HealthCheck(command, "pass", detail)


def command_version(command: str) -> str:
    try:
        completed = subprocess.run(
            [command, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""

    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0][:80] if output else ""


def check_openai_key() -> HealthCheck:
    if os.environ.get("OPENAI_API_KEY"):
        return HealthCheck("openai", "pass", "OPENAI_API_KEY is set")
    return HealthCheck("openai", "warn", "OPENAI_API_KEY is not set; live provider mode will be unavailable")
