"""Integrity checks for frozen external benchmark campaigns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifiedCampaignTask:
    name: str
    content_sha256: str
    path: Path


def task_tree_sha256(task_dir: Path) -> str:
    """Hash regular task files with their relative paths and sizes."""
    if not task_dir.is_dir():
        raise ValueError(f"task directory does not exist: {task_dir}")

    digest = hashlib.sha256()
    files = sorted(path for path in task_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"task directory contains no files: {task_dir}")

    for path in files:
        if path.is_symlink():
            raise ValueError(f"task directory contains a symbolic link: {path}")
        relative = path.relative_to(task_dir).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def verify_campaign(manifest_path: Path, dataset_dir: Path) -> list[VerifiedCampaignTask]:
    """Verify selected task bytes against a committed campaign manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported campaign manifest schema")

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("campaign manifest must contain at least one task")

    verified = []
    seen = set()
    for entry in tasks:
        if not isinstance(entry, dict):
            raise TypeError("campaign task entries must be objects")
        name = entry.get("name")
        expected = entry.get("content_sha256")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("campaign task names must be non-empty and unique")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"{name}: invalid content_sha256")

        task_dir = dataset_dir / name
        actual = task_tree_sha256(task_dir)
        if actual != expected:
            raise ValueError(f"{name}: task content hash mismatch")
        verified.append(VerifiedCampaignTask(name, actual, task_dir.resolve()))
        seen.add(name)
    return verified
