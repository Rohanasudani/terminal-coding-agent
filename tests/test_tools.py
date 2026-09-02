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
