from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shlex import split

from .models import ApprovalMode, ToolResult
from .safety import classify_command, resolve_inside_root


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, object]


@dataclass(frozen=True)
class PatchFile:
    path: str
    content: str


class ToolRegistry:
    def __init__(self, repo: Path, approval_mode: ApprovalMode, allow_network: bool = False) -> None:
        self.repo = repo.resolve()
        self.approval_mode = approval_mode
        self.allow_network = allow_network
        self._baseline = self._snapshot()

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "search",
                "Search repository text with ripgrep when available.",
                {"query": "string", "glob": "optional string"},
            ),
            ToolSpec(
                "read_file",
                "Read a UTF-8 text file inside the repository.",
                {"path": "string", "start": "optional int", "limit": "optional int"},
            ),
            ToolSpec(
                "plan_patch",
                "Preview a UTF-8 file write and return a unified diff without modifying the file.",
                {"path": "string", "content": "string"},
            ),
            ToolSpec(
                "plan_patch_set",
                "Preview multiple UTF-8 file writes as one grouped diff without modifying files.",
                {"files": [{"path": "string", "content": "string"}]},
            ),
            ToolSpec(
                "write_file",
                "Write a UTF-8 text file inside the repository and return a unified diff.",
                {"path": "string", "content": "string"},
            ),
            ToolSpec(
                "write_patch_set",
                "Write multiple UTF-8 files after a grouped plan and return a grouped diff.",
                {"files": [{"path": "string", "content": "string"}]},
            ),
            ToolSpec(
                "run_shell",
                "Run a shell command under the configured safety policy.",
                {"command": "string", "timeout": "optional int"},
            ),
            ToolSpec("git_diff", "Return the current git diff.", {}),
        ]

    def call(self, name: str, arguments: dict[str, object]) -> ToolResult:
        try:
            if name == "search":
                return self.search(str(arguments.get("query", "")), arguments.get("glob"))
            if name == "read_file":
                return self.read_file(
                    str(arguments.get("path", "")),
                    int(arguments.get("start", 1)),
                    int(arguments.get("limit", 200)),
                )
            if name == "plan_patch":
                return self.plan_patch(str(arguments.get("path", "")), str(arguments.get("content", "")))
            if name == "plan_patch_set":
                return self.plan_patch_set(arguments.get("files"))
            if name == "write_file":
                return self.write_file(str(arguments.get("path", "")), str(arguments.get("content", "")))
            if name == "write_patch_set":
                return self.write_patch_set(arguments.get("files"))
            if name == "run_shell":
                return self.run_shell(str(arguments.get("command", "")), int(arguments.get("timeout", 30)))
            if name == "git_diff":
                return self.git_diff()
        except (OSError, TypeError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
            return ToolResult("error", str(exc))

        return ToolResult("error", f"unknown tool: {name}")

    def search(self, query: str, glob: object | None = None) -> ToolResult:
        if not query:
            return ToolResult("error", "query is required")

        if shutil.which("rg"):
            command = ["rg", "-n", "--hidden", "--glob", "!.git"]
            if glob:
                command.extend(["--glob", str(glob)])
            command.append(query)
        else:
            command = ["grep", "-RIn", query, "."]

        completed = subprocess.run(
            command,
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        output = completed.stdout.strip() or completed.stderr.strip() or "no matches"
        return ToolResult("ok", output[:12_000], {"returncode": completed.returncode})

    def read_file(self, path: str, start: int = 1, limit: int = 200) -> ToolResult:
        target = resolve_inside_root(self.repo, path)
        if not target.is_file():
            return ToolResult("error", f"file not found: {path}")

        lines = target.read_text(encoding="utf-8").splitlines()
        start_index = max(start - 1, 0)
        selected = lines[start_index : start_index + max(limit, 1)]
        numbered = [f"{index + start_index + 1:>4} | {line}" for index, line in enumerate(selected)]
        return ToolResult("ok", "\n".join(numbered), {"path": str(target), "line_count": len(lines)})

    def plan_patch(self, path: str, content: str) -> ToolResult:
        target = resolve_inside_root(self.repo, path)
        relative_path = os.fspath(target.relative_to(self.repo))
        before = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
        after = content.splitlines(keepends=True)
        diff = self._unified_diff(relative_path, before, after)
        return ToolResult(
            "ok",
            diff or "file unchanged",
            {"path": str(target), "relative_path": relative_path, "content_sha256": sha256_text(content)},
        )

    def plan_patch_set(self, files: object) -> ToolResult:
        patch_files = coerce_patch_files(files)
        chunks: list[str] = []
        metadata_files: list[dict[str, str]] = []
        for patch_file in patch_files:
            target = resolve_inside_root(self.repo, patch_file.path)
            relative_path = os.fspath(target.relative_to(self.repo))
            before = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
            after = patch_file.content.splitlines(keepends=True)
            chunks.append(self._unified_diff(relative_path, before, after))
            metadata_files.append(
                {
                    "path": str(target),
                    "relative_path": relative_path,
                    "content_sha256": sha256_text(patch_file.content),
                }
            )

        return ToolResult("ok", "\n".join(chunk for chunk in chunks if chunk).strip() or "files unchanged", {"files": metadata_files})

    def write_file(self, path: str, content: str) -> ToolResult:
        target = resolve_inside_root(self.repo, path)
        relative_path = os.fspath(target.relative_to(self.repo))
        before = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
        after = content.splitlines(keepends=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        diff = self._unified_diff(relative_path, before, after)
        return ToolResult(
            "ok",
            diff or "file unchanged",
            {"path": str(target), "relative_path": relative_path, "content_sha256": sha256_text(content)},
        )

    def write_patch_set(self, files: object) -> ToolResult:
        patch_files = coerce_patch_files(files)
        planned: list[tuple[PatchFile, Path, str, list[str], list[str]]] = []
        for patch_file in patch_files:
            target = resolve_inside_root(self.repo, patch_file.path)
            relative_path = os.fspath(target.relative_to(self.repo))
            before = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
            after = patch_file.content.splitlines(keepends=True)
            planned.append((patch_file, target, relative_path, before, after))

        chunks: list[str] = []
        metadata_files: list[dict[str, str]] = []
        for patch_file, target, relative_path, before, after in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch_file.content, encoding="utf-8")
            chunks.append(self._unified_diff(relative_path, before, after))
            metadata_files.append(
                {
                    "path": str(target),
                    "relative_path": relative_path,
                    "content_sha256": sha256_text(patch_file.content),
                }
            )

        return ToolResult("ok", "\n".join(chunk for chunk in chunks if chunk).strip() or "files unchanged", {"files": metadata_files})

    def run_shell(self, command: str, timeout: int = 30) -> ToolResult:
        decision = classify_command(command, self.approval_mode, allow_network=self.allow_network)
        if decision.needs_approval:
            return ToolResult("blocked", decision.reason, {"command": command})
        if not decision.allowed:
            return ToolResult("blocked", decision.reason, {"command": command})
        parts = split(command)

        completed = subprocess.run(
            parts,
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=max(1, min(timeout, 120)),
            check=False,
        )
        output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
        return ToolResult("ok", output[:20_000] or "(no output)", {"returncode": completed.returncode})

    def git_diff(self) -> ToolResult:
        if self._is_git_repo():
            return self._git_diff()

        return ToolResult("ok", self._snapshot_diff(), {"source": "snapshot"})

    def _git_diff(self) -> ToolResult:
        completed = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        output = completed.stdout.strip() or "no diff"
        return ToolResult("ok", output[:20_000], {"returncode": completed.returncode})

    def _is_git_repo(self) -> bool:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    def _snapshot(self) -> dict[str, str]:
        files: dict[str, str] = {}
        ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".termagent"}
        for path in self.repo.rglob("*"):
            if not path.is_file() or ignored_dirs.intersection(path.relative_to(self.repo).parts):
                continue
            if path.stat().st_size > 1_000_000:
                continue
            try:
                files[os.fspath(path.relative_to(self.repo))] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        return files

    def _snapshot_diff(self) -> str:
        current = self._snapshot()
        chunks: list[str] = []
        for path in sorted(set(self._baseline) | set(current)):
            before = self._baseline.get(path, "").splitlines(keepends=True)
            after = current.get(path, "").splitlines(keepends=True)
            if before == after:
                continue
            chunks.append(
                "".join(
                    difflib.unified_diff(
                        before,
                        after,
                        fromfile=f"a/{path}",
                        tofile=f"b/{path}",
                    )
                )
            )
        return "".join(chunks).strip() or "no diff"

    @staticmethod
    def _unified_diff(relative_path: str, before: list[str], after: list[str]) -> str:
        return "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def coerce_patch_files(files: object) -> list[PatchFile]:
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty list")

    patch_files: list[PatchFile] = []
    for item in files:
        if not isinstance(item, dict):
            raise TypeError("each patch file must be an object")
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path:
            raise ValueError("each patch file requires a path")
        if not isinstance(content, str):
            raise TypeError("each patch file requires string content")
        patch_files.append(PatchFile(path=path, content=content))

    return patch_files
