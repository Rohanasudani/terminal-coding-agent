import json
from pathlib import Path

import pytest

from termagent.campaign import task_tree_sha256, verify_campaign


def write_manifest(path: Path, name: str, digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": [{"name": name, "content_sha256": digest}],
            }
        ),
        encoding="utf-8",
    )


def test_verify_campaign_accepts_exact_task_bytes(tmp_path: Path):
    task = tmp_path / "dataset" / "sample"
    task.mkdir(parents=True)
    (task / "instruction.md").write_text("Repair the project.\n", encoding="utf-8")
    manifest = tmp_path / "campaign.json"
    digest = task_tree_sha256(task)
    write_manifest(manifest, "sample", digest)

    verified = verify_campaign(manifest, tmp_path / "dataset")

    assert [(entry.name, entry.content_sha256) for entry in verified] == [("sample", digest)]


def test_verify_campaign_rejects_changed_task_bytes(tmp_path: Path):
    task = tmp_path / "dataset" / "sample"
    task.mkdir(parents=True)
    instruction = task / "instruction.md"
    instruction.write_text("Repair the project.\n", encoding="utf-8")
    manifest = tmp_path / "campaign.json"
    write_manifest(manifest, "sample", task_tree_sha256(task))
    instruction.write_text("A changed task.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="task content hash mismatch"):
        verify_campaign(manifest, tmp_path / "dataset")


def test_task_tree_hash_includes_relative_paths(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a.txt").write_text("same", encoding="utf-8")
    (second / "b.txt").write_text("same", encoding="utf-8")

    assert task_tree_sha256(first) != task_tree_sha256(second)
