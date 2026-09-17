from pathlib import Path

import pytest

from termagent.safety import classify_command, resolve_inside_root


def test_resolve_inside_root_blocks_path_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ValueError):
        resolve_inside_root(root, "../secret.txt")


def test_read_only_command_is_allowed():
    decision = classify_command("rg TODO", "suggest")

    assert decision.allowed is True
    assert decision.needs_approval is False


def test_destructive_command_is_blocked_even_in_auto_mode():
    decision = classify_command("rm -rf src", "auto")

    assert decision.allowed is False
    assert decision.needs_approval is False


def test_mutating_command_requires_approval_in_suggest_mode():
    decision = classify_command("python -m pytest -q", "suggest")

    assert decision.allowed is False
    assert decision.needs_approval is True


def test_network_command_is_blocked_by_default():
    decision = classify_command("curl https://example.com", "auto")

    assert decision.allowed is False
    assert decision.reason == "network command blocked by safety policy"


def test_inline_interpreter_execution_is_blocked():
    decision = classify_command("python -c 'print(1)'", "auto")

    assert decision.allowed is False
    assert decision.reason == "inline interpreter execution blocked by safety policy"


def test_shell_control_operator_is_blocked():
    decision = classify_command("pytest -q; touch hacked", "auto")

    assert decision.allowed is False
    assert decision.reason == "shell control operator blocked by safety policy"


def test_read_only_git_command_is_allowed():
    decision = classify_command("git status --short", "suggest")

    assert decision.allowed is True
    assert decision.needs_approval is False


def test_mutating_git_command_requires_approval():
    decision = classify_command("git checkout main", "suggest")

    assert decision.allowed is False
    assert decision.needs_approval is True


@pytest.mark.parametrize(
    "command",
    [
        "sed -i s/old/new/ app.py",
        "sed -i.bak s/old/new/ app.py",
        "sed --in-place=.bak s/old/new/ app.py",
        "find . -fprint files.txt",
        "git diff --output=changes.patch",
    ],
)
def test_mutating_options_cannot_bypass_suggest_approval(command: str):
    decision = classify_command(command, "suggest")

    assert decision.allowed is False
    assert decision.needs_approval is True


def test_nonmutating_sed_command_remains_read_only():
    decision = classify_command("sed -n 1,20p app.py", "suggest")

    assert decision.allowed is True
    assert decision.needs_approval is False


def test_find_delete_is_blocked_even_in_auto_mode():
    decision = classify_command("find . -name '*.tmp' -delete", "auto")

    assert decision.allowed is False
    assert decision.needs_approval is False
    assert decision.reason == "destructive command blocked by safety policy"


def test_find_exec_is_blocked_as_a_shell_control_sequence():
    decision = classify_command(r"find . -exec touch marker.txt \;", "auto")

    assert decision.allowed is False
    assert decision.needs_approval is False
