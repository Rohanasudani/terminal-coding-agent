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
