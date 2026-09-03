from pathlib import Path

from termagent.interactive import (
    InteractiveSettings,
    agent_config_for_task,
    help_text,
    interactive_banner,
    run_interactive_app,
)
from termagent.models import AgentConfig


def test_interactive_app_runs_tasks_until_quit(tmp_path: Path):
    prompts = iter(["fix tests", ":quit"])
    outputs: list[str] = []
    configs: list[AgentConfig] = []

    def fake_runner(config: AgentConfig) -> str:
        configs.append(config)
        return "done"

    status = run_interactive_app(
        InteractiveSettings(repo=tmp_path, approval_mode="auto"),
        input_fn=lambda _: next(prompts),
        output_fn=outputs.append,
        runner=fake_runner,
    )

    assert status == 0
    assert configs[0].task == "fix tests"
    assert configs[0].approval_mode == "auto"
    assert "done" in outputs
    assert outputs[-1] == "Session closed."


def test_interactive_app_handles_help_and_doctor(tmp_path: Path):
    prompts = iter([":help", ":doctor", ":quit"])
    outputs: list[str] = []

    status = run_interactive_app(
        InteractiveSettings(repo=tmp_path),
        input_fn=lambda _: next(prompts),
        output_fn=outputs.append,
        runner=lambda _: "unused",
    )

    assert status == 0
    assert any(":doctor" in output for output in outputs)
    assert any("repo" in output for output in outputs)


def test_agent_config_for_task_maps_interactive_settings(tmp_path: Path):
    config = agent_config_for_task(
        InteractiveSettings(
            repo=tmp_path,
            provider="mock",
            approval_mode="never",
            max_steps=3,
            test_command="pytest -q",
            allow_network_commands=True,
        ),
        "repair bug",
    )

    assert config.repo == tmp_path
    assert config.task == "repair bug"
    assert config.provider == "mock"
    assert config.approval_mode == "never"
    assert config.max_steps == 3
    assert config.test_command == "pytest -q"
    assert config.allow_network_commands is True


def test_interactive_text_is_human_readable(tmp_path: Path):
    assert "TermAgent interactive mode" in interactive_banner(InteractiveSettings(repo=tmp_path))
    assert "Example task" in help_text()
