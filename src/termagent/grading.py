from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shlex import split


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    output: str
    returncode: int | None


def grade_workspace(
    source: Path,
    candidate: Path,
    solution_files: list[str],
    command: str,
    *,
    timeout: float = 60,
) -> GradeResult:
    """Grade selected solution files against pristine tests in a fresh workspace.

    This is test isolation, not an OS sandbox. Only run trusted task code.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="termagent-grade-") as temp:
            workspace = Path(temp) / "repo"
            shutil.copytree(source, workspace, ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".git", ".termagent", ".venv",
            ))
            for name in solution_files:
                if not isinstance(name, str) or not name or Path(name).is_absolute():
                    raise ValueError("solution files must be relative paths")
                origin = (candidate / name).resolve()
                target = (workspace / name).resolve()
                if not origin.is_relative_to(candidate.resolve()) or not target.is_relative_to(workspace.resolve()):
                    raise ValueError(f"path escapes repository root: {name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)

            # Keep provider credentials and Python/pytest startup overrides out of graders.
            environment = {key: value for key, value in os.environ.items() if key in {
                "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
            }}
            environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            completed = subprocess.run(
                split(command), cwd=workspace, env=environment, text=True,
                capture_output=True, timeout=timeout, check=False,
            )
            output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
            return GradeResult(completed.returncode == 0, output[:20_000], completed.returncode)
    except subprocess.TimeoutExpired:
        return GradeResult(False, "Verifier timed out.", None)
    except (OSError, ValueError) as exc:
        return GradeResult(False, f"Verifier could not run: {exc}", None)
