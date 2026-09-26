from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shlex import split

from .code_map import build_code_map, format_code_map, format_references, validate_python_source
from .completion import validate_completion_review
from .models import ApprovalMode, ToolResult
from .planning import validate_task_plan
from .safety import classify_command, resolve_inside_root

SNAPSHOT_IGNORED_DIRS = frozenset({
    ".git", ".venv", ".next", ".termagent", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "__pycache__",
    "node_modules", "dist", "build", "coverage", "target",
})
SNAPSHOT_PRIVATE_NAMES = frozenset({
    ".env", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519",
})


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
        self._git_repo_at_start = self._is_git_repo()
        self._baseline_head = self._git_head() if self._git_repo_at_start else None
        self._baseline = self._snapshot()

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "set_task_plan",
                "Register the task goal, expected output files, and acceptance checks.",
                {
                    "summary": "string",
                    "expected_paths": ["string"],
                    "acceptance_checks": ["string"],
                },
            ),
            ToolSpec(
                "submit_completion_review",
                "Review each acceptance check against observed evidence before finishing.",
                {
                    "acceptance_evidence": [{"criterion": "string", "evidence": "string"}],
                    "residual_risks": ["string"],
                    "ready": "boolean",
                },
            ),
            ToolSpec(
                "search",
                "Search repository text with consistent extended regular expressions.",
                {
                    "query": "string",
                    "glob": "optional string",
                    "include_ignored": "optional boolean",
                },
            ),
            ToolSpec(
                "list_files",
                "List repository files without following symbolic links.",
                {
                    "path": "optional string",
                    "glob": "optional string",
                    "limit": "optional int",
                    "include_ignored": "optional boolean",
                },
            ),
            ToolSpec(
                "read_file",
                "Read a UTF-8 text file inside the repository.",
                {"path": "string", "start": "optional int", "limit": "optional int"},
            ),
            ToolSpec(
                "code_map",
                "Build a Python, JavaScript, and TypeScript code map with symbols and imports.",
                {"query": "optional string", "limit": "optional int"},
            ),
            ToolSpec(
                "find_references",
                "Find Python, JavaScript, and TypeScript name references for a symbol.",
                {"symbol": "string", "limit": "optional int"},
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
            if name == "set_task_plan":
                return self.set_task_plan(
                    arguments.get("summary"),
                    arguments.get("expected_paths"),
                    arguments.get("acceptance_checks"),
                )
            if name == "submit_completion_review":
                return self.submit_completion_review(
                    arguments.get("acceptance_evidence"),
                    arguments.get("residual_risks"),
                    arguments.get("ready"),
                )
            if name == "search":
                return self.search(
                    str(arguments.get("query", "")),
                    arguments.get("glob"),
                    arguments.get("include_ignored", False),
                )
            if name == "list_files":
                return self.list_files(
                    arguments.get("path", "."),
                    arguments.get("glob"),
                    arguments.get("limit", 200),
                    arguments.get("include_ignored", False),
                )
            if name == "read_file":
                return self.read_file(
                    str(arguments.get("path", "")),
                    int(arguments.get("start", 1)),
                    int(arguments.get("limit", 200)),
                )
            if name == "code_map":
                query = arguments.get("query")
                return self.code_map(
                    str(query) if query is not None else None,
                    int(arguments.get("limit", 80)),
                )
            if name == "find_references":
                return self.find_references(
                    str(arguments.get("symbol", "")),
                    int(arguments.get("limit", 120)),
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

    def set_task_plan(
        self,
        summary: object,
        expected_paths: object,
        acceptance_checks: object,
    ) -> ToolResult:
        plan = validate_task_plan(self.repo, summary, expected_paths, acceptance_checks)
        metadata = {
            "summary": plan.summary,
            "expected_paths": list(plan.expected_paths),
            "acceptance_checks": list(plan.acceptance_checks),
        }
        lines = [f"Goal: {plan.summary}"]
        lines.append("Expected paths: " + (", ".join(plan.expected_paths) or "not known yet"))
        lines.append(
            "Acceptance checks: "
            + "; ".join(
                f"C{index}: {check}" for index, check in enumerate(plan.acceptance_checks, start=1)
            )
        )
        return ToolResult("ok", "\n".join(lines), metadata)

    def submit_completion_review(
        self,
        acceptance_evidence: object,
        residual_risks: object,
        ready: object,
    ) -> ToolResult:
        review = validate_completion_review(acceptance_evidence, residual_risks, ready)
        metadata = {
            "acceptance_evidence": [
                {"criterion": item.criterion, "evidence": item.evidence}
                for item in review.acceptance_evidence
            ],
            "residual_risks": list(review.residual_risks),
            "ready": review.ready,
        }
        status = "ready" if review.ready else "not ready"
        return ToolResult("ok", f"Completion review recorded: {status}.", metadata)

    def search(
        self,
        query: str,
        glob: object | None = None,
        include_ignored: object = False,
    ) -> ToolResult:
        if not query:
            return ToolResult("error", "query is required")
        if not isinstance(include_ignored, bool):
            raise TypeError("include_ignored must be a boolean")

        if shutil.which("rg"):
            command = ["rg", "-n", "--hidden", "--glob", "!.git"]
            command.extend(self._private_exclusion_globs())
            if include_ignored:
                command.append("--no-ignore")
            if glob:
                command.extend(["--glob", str(glob)])
            command.extend(["--", query])
        elif self._is_git_repo() and not include_ignored:
            command = ["git", "grep", "-n", "-E", "-e", query, "--"]
            command.extend([
                str(glob) if glob else ".",
                ":(exclude)**/.env", ":(exclude)**/.env.*",
                ":(exclude)**/.npmrc", ":(exclude)**/.pypirc",
                ":(exclude)**/.netrc", ":(exclude)**/id_rsa",
                ":(exclude)**/id_ed25519", ":(exclude)**/*.pem",
                ":(exclude)**/*.p12", ":(exclude)**/*.pfx",
            ])
        else:
            command = [
                "grep", "-REIn", "--exclude-dir=.git",
                "--exclude=.env", "--exclude=.env.*", "--exclude=.npmrc",
                "--exclude=.pypirc", "--exclude=.netrc", "--exclude=id_rsa",
                "--exclude=id_ed25519", "--exclude=*.pem", "--exclude=*.p12",
                "--exclude=*.pfx",
            ]
            if glob:
                command.append(f"--include={glob}")
            command.extend(["-e", query, "--", "."])

        completed = subprocess.run(
            command,
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        raw_output = completed.stdout.strip() or completed.stderr.strip() or "no matches"
        truncated = len(raw_output) > 12_000
        output = raw_output[:11_970] + "\n[search output truncated]" if truncated else raw_output
        return ToolResult(
            "ok",
            output,
            {
                "returncode": completed.returncode,
                "match_lines": len(completed.stdout.splitlines()),
                "truncated": truncated,
                "include_ignored": include_ignored,
            },
        )

    def list_files(
        self,
        path: object = ".",
        glob: object | None = None,
        limit: object = 200,
        include_ignored: object = False,
    ) -> ToolResult:
        if not isinstance(path, str) or not path:
            raise TypeError("path must be a non-empty string")
        if glob is not None and not isinstance(glob, str):
            raise TypeError("glob must be a string when provided")
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise TypeError("limit must be an integer")
        if not isinstance(include_ignored, bool):
            raise TypeError("include_ignored must be a boolean")
        target = resolve_inside_root(self.repo, path)
        if not target.exists():
            return ToolResult("error", f"path not found: {path}")

        candidates = self._listed_paths(target, include_ignored=include_ignored)
        if glob:
            candidates = [candidate for candidate in candidates if candidate.match(glob)]
        bounded_limit = max(1, min(limit, 1_000))
        truncated = len(candidates) > bounded_limit
        selected = candidates[:bounded_limit]
        output = "\n".join(candidate.as_posix() for candidate in selected) or "no files"
        if truncated:
            output += "\n[file list truncated]"
        return ToolResult(
            "ok",
            output,
            {
                "count": len(candidates),
                "returned": len(selected),
                "truncated": truncated,
                "include_ignored": include_ignored,
            },
        )

    def read_file(self, path: str, start: int = 1, limit: int = 200) -> ToolResult:
        target = resolve_inside_root(self.repo, path)
        if not target.is_file():
            return ToolResult("error", f"file not found: {path}")

        lines = target.read_text(encoding="utf-8").splitlines()
        start_index = max(start - 1, 0)
        selected = lines[start_index : start_index + max(limit, 1)]
        numbered = [f"{index + start_index + 1:>4} | {line}" for index, line in enumerate(selected)]
        return ToolResult("ok", "\n".join(numbered), {"path": str(target), "line_count": len(lines)})

    def code_map(self, query: str | None = None, limit: int = 80) -> ToolResult:
        code_map = build_code_map(self.repo)
        output = format_code_map(code_map, query=query, limit=max(1, min(limit, 500)))
        return ToolResult(
            "ok",
            output[:20_000],
            {
                "symbols": len(code_map.symbols),
                "imports": len(code_map.imports),
                "references": len(code_map.references),
                "parse_errors": len(code_map.parse_errors),
            },
        )

    def find_references(self, symbol: str, limit: int = 120) -> ToolResult:
        if not symbol:
            return ToolResult("error", "symbol is required")
        code_map = build_code_map(self.repo)
        output = format_references(code_map, symbol, limit=max(1, min(limit, 500)))
        return ToolResult("ok", output[:20_000], {"symbol": symbol})

    def plan_patch(self, path: str, content: str) -> ToolResult:
        target = resolve_inside_root(self.repo, path)
        relative_path = os.fspath(target.relative_to(self.repo))
        syntax_error = validate_python_source(relative_path, content)
        if syntax_error:
            return ToolResult("error", f"python syntax check failed: {syntax_error}")
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
            syntax_error = validate_python_source(relative_path, patch_file.content)
            if syntax_error:
                return ToolResult("error", f"python syntax check failed: {syntax_error}")
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
        syntax_error = validate_python_source(relative_path, content)
        if syntax_error:
            return ToolResult("error", f"python syntax check failed: {syntax_error}")
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
            syntax_error = validate_python_source(relative_path, patch_file.content)
            if syntax_error:
                return ToolResult("error", f"python syntax check failed: {syntax_error}")
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

        if self._git_repo_at_start:
            return ToolResult("error", "Git is unavailable; cannot produce a complete final diff")

        return ToolResult("ok", self._snapshot_diff(), {"source": "snapshot"})

    def has_changes(self) -> bool:
        result = self.git_diff()
        return result.status == "ok" and result.output.strip() not in {"", "no diff"}

    def _git_diff(self) -> ToolResult:
        baseline = self._baseline_head or "HEAD"
        completed = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-textconv", baseline, "--", "."],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            head = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"], cwd=self.repo,
                capture_output=True, timeout=20, check=False,
            )
            if head.returncode == 0:
                return ToolResult("error", "Git could not produce a complete final diff")
            # An initialized repository may not have a HEAD commit yet.
            unstaged = subprocess.run(
                ["git", "diff", "--no-ext-diff", "--no-textconv", "--", "."],
                cwd=self.repo, text=True,
                capture_output=True, timeout=20, check=False,
            )
            staged = subprocess.run(
                ["git", "diff", "--no-ext-diff", "--no-textconv", "--cached", "--", "."],
                cwd=self.repo,
                text=True, capture_output=True, timeout=20, check=False,
            )
            if unstaged.returncode != 0 or staged.returncode != 0:
                return ToolResult("error", "Git could not produce a complete final diff")
            tracked_diff = "\n".join(part for part in (staged.stdout.strip(), unstaged.stdout.strip()) if part)
        else:
            tracked_diff = completed.stdout.strip()

        untracked_diff = self._snapshot_diff(exclude_paths=self._git_tracked_paths())
        combined = "\n".join(
            part for part in (tracked_diff, untracked_diff if untracked_diff != "no diff" else "") if part
        ) or "no diff"
        truncated = len(combined) > 20_000
        return ToolResult(
            "ok", combined[:19_970] + "\n[diff truncated]" if truncated else combined,
            {
                "source": "git+snapshot",
                "truncated": truncated,
                "baseline_head": self._baseline_head,
                "current_head": self._git_head(),
            },
        )

    def _is_git_repo(self) -> bool:
        if shutil.which("git") is None:
            return False
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo,
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except OSError:
            return False
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    def _git_head(self) -> str | None:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        value = completed.stdout.strip()
        return value if completed.returncode == 0 and len(value) == 40 else None

    def _listed_paths(self, target: Path, *, include_ignored: bool) -> list[Path]:
        if target.is_file():
            relative = target.relative_to(self.repo)
            return [] if self._skip_snapshot_path(relative) else [relative]

        if self._is_git_repo() and not include_ignored:
            completed = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
                cwd=self.repo,
                capture_output=True,
                timeout=20,
                check=False,
            )
            if completed.returncode != 0:
                raise OSError("Git could not list repository files")
            prefix = target.relative_to(self.repo)
            paths = [Path(os.fsdecode(item)) for item in completed.stdout.split(b"\0") if item]
            return sorted(
                candidate
                for candidate in paths
                if (prefix == Path(".") or candidate == prefix or prefix in candidate.parents)
                and not self._skip_snapshot_path(candidate)
            )

        paths = []
        for root, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [
                name for name in dirs
                if name not in SNAPSHOT_IGNORED_DIRS and not (Path(root) / name).is_symlink()
            ]
            for name in files:
                candidate = Path(root) / name
                relative = candidate.relative_to(self.repo)
                if candidate.is_symlink() or self._skip_snapshot_path(relative):
                    continue
                paths.append(relative)
        return sorted(paths)

    @staticmethod
    def _private_exclusion_globs() -> list[str]:
        return [
            "--glob", "!.env", "--glob", "!.env.*", "--glob", "!.npmrc",
            "--glob", "!.pypirc", "--glob", "!.netrc", "--glob", "!id_rsa",
            "--glob", "!id_ed25519", "--glob", "!*.pem", "--glob", "!*.p12",
            "--glob", "!*.pfx",
        ]

    def _snapshot(self) -> dict[str, str]:
        # TODO: Index non-Git baselines incrementally for very large source trees.
        files: dict[str, str] = {}
        if self._is_git_repo():
            paths = (self.repo / path for path in self._git_untracked_paths())
        else:
            paths = self._walk_snapshot_paths()
        for path in paths:
            try:
                relative_path = path.relative_to(self.repo)
                if self._skip_snapshot_path(relative_path):
                    continue
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
                    continue
                files[os.fspath(relative_path)] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        return files

    @staticmethod
    def _skip_snapshot_path(path: Path) -> bool:
        name = path.name.lower()
        if SNAPSHOT_IGNORED_DIRS.intersection(path.parts[:-1]):
            return True
        if name in SNAPSHOT_PRIVATE_NAMES or (
            name.startswith(".env.")
            and name not in {".env.example", ".env.sample", ".env.template"}
        ):
            return True
        return path.suffix.lower() in {".pem", ".p12", ".pfx"}

    def _walk_snapshot_paths(self):
        for root, dirs, files in os.walk(self.repo, followlinks=False):
            dirs[:] = [
                name for name in dirs
                if name not in SNAPSHOT_IGNORED_DIRS and not (Path(root) / name).is_symlink()
            ]
            for name in files:
                yield Path(root) / name

    def _git_untracked_paths(self) -> set[str]:
        completed = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=self.repo, capture_output=True, timeout=20, check=False,
        )
        if completed.returncode != 0:
            raise OSError("Git could not list untracked files for the snapshot")
        return {os.fsdecode(path) for path in completed.stdout.split(b"\0") if path}

    def _git_tracked_paths(self) -> set[str]:
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "-z", "--", "."],
            cwd=self.repo, capture_output=True, timeout=20, check=False,
        )
        if completed.returncode != 0:
            raise OSError("Git could not list tracked files for the final diff")
        return {os.fsdecode(path) for path in completed.stdout.split(b"\0") if path}

    def _snapshot_diff(self, *, exclude_paths: set[str] | None = None) -> str:
        current = self._snapshot()
        chunks: list[str] = []
        removed = {path for path in self._baseline if not (self.repo / path).exists()}
        for path in sorted(set(current) | removed):
            if exclude_paths and path in exclude_paths:
                continue
            before = self._baseline.get(path, "").splitlines(keepends=True)
            after = current.get(path, "").splitlines(keepends=True)
            if before == after and (path in self._baseline) == (path in current):
                continue
            diff = "".join(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            chunks.append(diff or f"--- a/{path}\n+++ b/{path}\n")
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
