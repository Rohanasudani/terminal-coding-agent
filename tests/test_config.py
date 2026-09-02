from pathlib import Path

import pytest

from termagent.config import apply_config_file
from termagent.models import AgentConfig


def test_apply_config_file_overrides_agent_defaults(tmp_path: Path):
    config_path = tmp_path / "termagent.toml"
    config_path.write_text(
        """
        [termagent]
        provider = "openai"
        model = "gpt-5.6-terra"
        approval_mode = "auto"
        max_steps = 20
        test_command = "uv run pytest -q"
        provider_retries = 3
        log_dir = ".termagent/custom"
        """,
        encoding="utf-8",
    )

    config = apply_config_file(AgentConfig(repo=tmp_path, task="fix tests"), config_path)

    assert config.provider == "openai"
    assert config.model == "gpt-5.6-terra"
    assert config.approval_mode == "auto"
    assert config.max_steps == 20
    assert config.test_command == "uv run pytest -q"
    assert config.provider_retries == 3
    assert config.log_dir == Path(".termagent/custom")


def test_config_file_rejects_unknown_keys(tmp_path: Path):
    config_path = tmp_path / "termagent.toml"
    config_path.write_text("[termagent]\nunknown = true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown config key"):
        apply_config_file(AgentConfig(repo=tmp_path, task="fix tests"), config_path)
