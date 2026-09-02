from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shlex import split

from .models import ApprovalMode


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    needs_approval: bool
    reason: str


READ_ONLY_COMMANDS = {
    "cat",
    "find",
    "git",
    "grep",
    "head",
    "ls",
    "pwd",
    "rg",
    "sed",
    "tail",
    "test",
    "wc",
}

DESTRUCTIVE_TOKENS = {
    "rm",
    "rmdir",
    "mv",
    "chmod",
    "chown",
    "sudo",
    "dd",
    "mkfs",
    "kill",
    "pkill",
    "shutdown",
    "reboot",
}

WRITE_HINTS = {
    ">",
    ">>",
    "tee",
    "python",
    "python3",
    "node",
    "npm",
    "pip",
    "uv",
    "cargo",
    "go",
    "make",
}


def resolve_inside_root(root: Path, candidate: str | Path) -> Path:
    root = root.resolve()
    path = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()

    if path != root and root not in path.parents:
        raise ValueError(f"path escapes repository root: {candidate}")

    return path


def classify_command(command: str, approval_mode: ApprovalMode) -> SafetyDecision:
    try:
        parts = split(command)
    except ValueError as exc:
        return SafetyDecision(False, False, f"command could not be parsed: {exc}")

    if not parts:
        return SafetyDecision(False, False, "empty command")

    executable = Path(parts[0]).name
    tokens = {Path(part).name if "/" in part else part for part in parts}

    if executable in DESTRUCTIVE_TOKENS or tokens.intersection(DESTRUCTIVE_TOKENS):
        return SafetyDecision(False, False, "destructive command blocked by safety policy")

    if executable in READ_ONLY_COMMANDS and not tokens.intersection(WRITE_HINTS):
        return SafetyDecision(True, False, "read-only command allowed")

    if approval_mode == "auto":
        return SafetyDecision(True, False, "approval mode allows command")

    if approval_mode == "suggest":
        return SafetyDecision(False, True, "command requires human approval")

    return SafetyDecision(False, False, "approval mode is never")

