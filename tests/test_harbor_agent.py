import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("harbor", reason="optional Harbor integration requires .[harbor] on Python 3.12+")

from harbor.environments.base import ExecResult
from harbor.models.agent.context import AgentContext

from termagent.harbor_agent import TermAgentHarbor


def make_agent(tmp_path, **kwargs):
    wheels = tmp_path / "wheels"
    wheels.mkdir(exist_ok=True)
    (wheels / "terminal_coding_agent-0.1.0-py3-none-any.whl").write_bytes(b"test wheel")
    return TermAgentHarbor(
        logs_dir=tmp_path / "logs", wheel_dir=str(wheels),
        test_command="python -m pytest -q", **kwargs,
    )


def test_live_adapter_requires_explicit_model(tmp_path):
    with pytest.raises(ValueError, match="explicit model"):
        make_agent(tmp_path)


def test_adapter_install_uses_uploaded_wheels_offline(tmp_path):
    agent = make_agent(tmp_path, provider="repair")
    environment = AsyncMock()
    environment.exec.return_value = ExecResult(return_code=0)
    asyncio.run(agent.setup(environment))
    assert environment.upload_dir.await_count == 1
    assert all(call.kwargs["user"] == "root" for call in environment.exec.await_args_list)
    assert "--no-index" in environment.exec.await_args_list[-1].kwargs["command"]
    assert agent.version().startswith("wheel-sha256:")


def test_prompt_is_uploaded_as_data_and_credentials_are_not_in_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    agent = make_agent(tmp_path, model_name="openai/test-model", controller_recovery=False)
    environment = AsyncMock()
    environment.exec.return_value = ExecResult(return_code=1, stdout="incomplete")
    uploaded = {}

    async def upload(source, target):
        uploaded.update(json.loads(Path(source).read_text()))

    async def download(source, target):
        Path(target).write_text(json.dumps({
            "input_tokens": 20, "output_tokens": 10, "estimated_cost_usd": 0.01,
            "completed": False, "tests_passed": False, "steps": 3,
            "usage_is_complete": True,
        }))

    environment.upload_file.side_effect = upload
    environment.download_file.side_effect = download
    context = AgentContext()
    prompt = "fix 'quoted' input; $(touch /tmp/not-a-command)"
    asyncio.run(agent.run(prompt, environment, context))
    assert uploaded["task"] == prompt
    assert uploaded["model"] == "test-model"
    assert uploaded["controller_recovery"] is False
    assert uploaded["require_changes"] is True
    assert uploaded["task_planning"] is True
    assert uploaded["max_stagnation_events"] == 2
    assert "test-only-secret" not in json.dumps(uploaded)
    call = environment.exec.await_args.kwargs
    assert prompt not in call["command"]
    assert "test-only-secret" not in call["command"]
    assert call["env"] == {"OPENAI_API_KEY": "test-only-secret"}
    assert context.n_input_tokens == 20
    assert context.metadata["completed"] is False
    assert context.metadata["max_output_tokens"] == 4096
    assert context.metadata["reasoning_effort"] == "high"
    assert context.metadata["usage_is_complete"] is True
    assert context.metadata["require_changes"] is True
    assert context.metadata["task_planning"] is True
    assert context.metadata["max_stagnation_events"] == 2


def test_missing_key_fails_before_agent_process(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent = make_agent(tmp_path, model_name="test-model")
    environment = AsyncMock()
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(agent.run("fix", environment, AgentContext()))
    environment.exec.assert_not_awaited()
