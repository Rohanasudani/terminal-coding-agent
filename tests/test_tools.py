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


def test_shell_blocks_destructive_commands(tmp_path: Path):
    tools = ToolRegistry(tmp_path, "auto")

    result = tools.call("run_shell", {"command": "rm -rf ."})

    assert result.status == "blocked"

