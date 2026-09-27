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
def test_known_file_mutations_are_blocked_in_every_approval_mode(command: str):
    for approval_mode in ("never", "suggest", "auto"):
        decision = classify_command(command, approval_mode)

        assert decision.allowed is False
        assert decision.needs_approval is False
        assert decision.reason == "file-mutating command option blocked; use the patch tools"


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


def test_nul_byte_is_rejected_before_subprocess_execution():
    decision = classify_command("pytest\x00-q", "auto")

    assert decision.allowed is False
    assert decision.reason == "NUL byte blocked by safety policy"


@pytest.mark.parametrize("command", ["cat .env", "sed -n 1,5p config/.env.local", "git show HEAD:.env"])
def test_shell_commands_cannot_read_private_credential_paths(command: str):
    decision = classify_command(command, "auto")

    assert decision.allowed is False
    assert decision.reason == "private credential file blocked by safety policy"


def test_shell_commands_can_read_environment_templates():
    decision = classify_command("cat .env.example", "suggest")

    assert decision.allowed is True
