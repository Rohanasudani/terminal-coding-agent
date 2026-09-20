import subprocess
from pathlib import Path

from termagent.tools import ToolRegistry


def test_read_and_write_file_stay_inside_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "hello.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    tools = ToolRegistry(repo, "auto")
    read = tools.call("read_file", {"path": "hello.py"})
    write = tools.call("write_file", {"path": "hello.py", "content": "print('bye')\n"})

    assert read.status == "ok"
    assert "print('hi')" in read.output
    assert write.status == "ok"
    assert "-print('hi')" in write.output
    assert "+print('bye')" in write.output
    assert "a/hello.py" in write.output


def test_plan_patch_previews_without_writing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "hello.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    tools = ToolRegistry(repo, "auto")
    result = tools.call("plan_patch", {"path": "hello.py", "content": "print('bye')\n"})

    assert result.status == "ok"
    assert "-print('hi')" in result.output
    assert "+print('bye')" in result.output
    assert target.read_text(encoding="utf-8") == "print('hi')\n"
    assert "content_sha256" in result.metadata


def test_plan_patch_rejects_invalid_python(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "auto")

    result = tools.call("plan_patch", {"path": "broken.py", "content": "def broken(:\n    pass\n"})

    assert result.status == "error"
    assert "python syntax check failed" in result.output


def test_code_map_and_references_tools(tmp_path: Path):
    (tmp_path / "module.py").write_text(
        "def normalize(value):\n    return value.strip()\n\nresult = normalize(' x ')\n",
        encoding="utf-8",
    )
    tools = ToolRegistry(tmp_path, "auto")

    code_map = tools.call("code_map", {"query": "normalize"})
    references = tools.call("find_references", {"symbol": "normalize"})

    assert code_map.status == "ok"
    assert "function normalize at module.py:1" in code_map.output
    assert references.status == "ok"
    assert "module.py:4" in references.output


def test_patch_set_previews_and_writes_grouped_diff(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    first = repo / "first.py"
    second = repo / "second.py"
    first.write_text("value = 1\n", encoding="utf-8")
    second.write_text("name = 'old'\n", encoding="utf-8")
    files = [
        {"path": "first.py", "content": "value = 2\n"},
        {"path": "second.py", "content": "name = 'new'\n"},
    ]

    tools = ToolRegistry(repo, "auto")
    planned = tools.call("plan_patch_set", {"files": files})
    written = tools.call("write_patch_set", {"files": files})

    assert planned.status == "ok"
    assert written.status == "ok"
    assert "a/first.py" in planned.output
    assert "a/second.py" in planned.output
    assert first.read_text(encoding="utf-8") == "value = 2\n"
    assert second.read_text(encoding="utf-8") == "name = 'new'\n"
    assert len(written.metadata["files"]) == 2


def test_patch_set_rejects_malformed_files_safely(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "auto")

    result = tools.call("plan_patch_set", {"files": ["bad"]})

    assert result.status == "error"
    assert "patch file must be an object" in result.output


def test_shell_blocks_destructive_commands(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "auto")

    result = tools.call("run_shell", {"command": "rm -rf ."})

    assert result.status == "blocked"


def test_git_diff_falls_back_to_snapshot_outside_git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    target.write_text("value = 2\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "-value = 1" in result.output
    assert "+value = 2" in result.output


def test_git_diff_falls_back_to_snapshot_when_git_is_unavailable(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    target.write_text("value = 2\n", encoding="utf-8")
    monkeypatch.setattr("termagent.tools.shutil.which", lambda command: None)
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert result.metadata["source"] == "snapshot"
    assert "-value = 1" in result.output
    assert "+value = 2" in result.output


def test_git_diff_includes_new_untracked_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    tools = ToolRegistry(repo, "auto")

    (repo / "new.py").write_text("value = 1\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "a/new.py" in result.output
    assert "+value = 1" in result.output


def test_git_diff_combines_tracked_staged_and_untracked_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "staged.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py", "staged.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
        cwd=repo, check=True,
    )
    (repo / "loose.py").write_text("value = 5\n", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    (repo / "tracked.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "staged.py").write_text("value = 3\n", encoding="utf-8")
    (repo / "new.py").write_text("value = 4\n", encoding="utf-8")
    (repo / "loose.py").write_text("value = 6\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.py"], cwd=repo, check=True)
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "+value = 2" in result.output
    assert "+value = 3" in result.output
    assert "a/new.py" in result.output
    assert "+value = 4" in result.output
    assert "-value = 5" in result.output
    assert "+value = 6" in result.output
    assert result.metadata["source"] == "git+snapshot"


def test_git_diff_excludes_ignored_files_and_external_symlinks(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".env\nnode_modules/\n", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("private before\n", encoding="utf-8")
    (repo / "linked.txt").symlink_to(outside)
    tools = ToolRegistry(repo, "auto")

    (repo / ".env").write_text("secret credential\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "generated.js").write_text("generated secret\n", encoding="utf-8")
    outside.write_text("private after\n", encoding="utf-8")
    (repo / "new.py").write_text("value = 1\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "a/new.py" in result.output
    assert "secret credential" not in result.output
    assert "generated secret" not in result.output
    assert "private after" not in result.output


def test_non_git_snapshot_skips_symlinks_and_generated_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private before\n", encoding="utf-8")
    (repo / "linked.txt").symlink_to(outside)
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "generated.js").write_text("generated before\n", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    outside.write_text("private after\n", encoding="utf-8")
    (repo / "node_modules" / "generated.js").write_text("generated after\n", encoding="utf-8")
    (repo / "source.py").write_text("value = 1\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "a/source.py" in result.output
    assert "private after" not in result.output
    assert "generated after" not in result.output


def test_snapshot_excludes_local_credential_files_without_gitignore(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tools = ToolRegistry(repo, "auto")

    (repo / ".env").write_text("API_KEY=private-value\n", encoding="utf-8")
    (repo / ".npmrc").write_text("token=private-value\n", encoding="utf-8")
    (repo / "server.pem").write_text("private-value\n", encoding="utf-8")
    (repo / "source.py").write_text("value = 1\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "source.py" in result.output
    assert "private-value" not in result.output


def test_git_repo_does_not_claim_complete_diff_if_git_disappears(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    tools = ToolRegistry(repo, "auto")

    monkeypatch.setattr("termagent.tools.shutil.which", lambda command: None)
    result = tools.call("git_diff", {})

    assert result.status == "error"
    assert "complete final diff" in result.output


def test_git_diff_is_scoped_to_selected_subdirectory(tmp_path: Path):
    repo = tmp_path / "repo"
    work = repo / "work"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (work / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "work/tracked.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
        cwd=repo, check=True,
    )
    tools = ToolRegistry(work, "auto")

    (work / "tracked.py").write_text("value = 2\n", encoding="utf-8")
    (work / "new.py").write_text("value = 3\n", encoding="utf-8")
    (repo / "outside.py").write_text("value = 4\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "+value = 2" in result.output
    assert "+value = 3" in result.output
    assert "outside.py" not in result.output


def test_git_diff_marks_truncated_output(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    tools = ToolRegistry(repo, "auto")

    (repo / "large.txt").write_text("x" * 25_000 + "\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert result.metadata["truncated"] is True
    assert result.output.endswith("[diff truncated]")


def test_new_ignore_rule_does_not_report_existing_file_as_deleted(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "local.txt").write_text("private value\n", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    (repo / ".gitignore").write_text("local.txt\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "a/.gitignore" in result.output
    assert "local.txt" in result.output
    assert "private value" not in result.output


def test_snapshot_reports_empty_file_creation_and_real_deletion(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "old.txt").write_text("", encoding="utf-8")
    tools = ToolRegistry(repo, "auto")

    (repo / "old.txt").unlink()
    (repo / "new.txt").write_text("", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "a/old.txt" in result.output
    assert "a/new.txt" in result.output


def test_git_diff_does_not_execute_repository_external_diff(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    target = repo / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "module.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
        cwd=repo, check=True,
    )
    marker = tmp_path / "external-diff-ran"
    helper = tmp_path / "external-diff.sh"
    helper.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    helper.chmod(0o700)
    subprocess.run(["git", "config", "diff.external", str(helper)], cwd=repo, check=True)
    tools = ToolRegistry(repo, "auto")

    target.write_text("value = 2\n", encoding="utf-8")
    result = tools.call("git_diff", {})

    assert result.status == "ok"
    assert "+value = 2" in result.output
    assert not marker.exists()
