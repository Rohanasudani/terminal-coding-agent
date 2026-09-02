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

READ_ONLY_GIT_SUBCOMMANDS = {
    "diff",
    "grep",
    "log",
    "ls-files",
    "rev-parse",
    "show",
    "status",
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

NETWORK_COMMANDS = {
    "curl",
    "ftp",
    "nc",
    "netcat",
    "rsync",
    "scp",
    "sftp",
    "ssh",
    "telnet",
    "wget",
}

INLINE_EXEC_FLAGS = {"-c", "-e"}
INLINE_EXECUTABLES = {"bash", "node", "perl", "python", "python3", "ruby", "sh", "zsh"}
SHELL_METACHARS = {"&&", "||", ";", "|", "$(", "`"}

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


def classify_command(
    command: str,
    approval_mode: ApprovalMode,
    allow_network: bool = False,
) -> SafetyDecision:
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

    if not allow_network and (executable in NETWORK_COMMANDS or tokens.intersection(NETWORK_COMMANDS)):
        return SafetyDecision(False, False, "network command blocked by safety policy")

    if is_inline_interpreter(executable) and tokens.intersection(INLINE_EXEC_FLAGS):
        return SafetyDecision(False, False, "inline interpreter execution blocked by safety policy")

    if any(marker in command for marker in SHELL_METACHARS):
        return SafetyDecision(False, False, "shell control operator blocked by safety policy")

    if executable == "git" and len(parts) > 1 and parts[1] in READ_ONLY_GIT_SUBCOMMANDS:
        return SafetyDecision(True, False, "read-only git command allowed")

    if executable in READ_ONLY_COMMANDS and not tokens.intersection(WRITE_HINTS):
        return SafetyDecision(True, False, "read-only command allowed")

    if approval_mode == "auto":
        return SafetyDecision(True, False, "approval mode allows command")

    if approval_mode == "suggest":
        return SafetyDecision(False, True, "command requires human approval")

    return SafetyDecision(False, False, "approval mode is never")


def is_inline_interpreter(executable: str) -> bool:
    return executable in INLINE_EXECUTABLES or executable.startswith("python")
