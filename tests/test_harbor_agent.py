import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("harbor", reason="optional Harbor integration requires .[harbor] on Python 3.12+")

from harbor.environments.base import ExecResult
from harbor.models.agent.context import AgentContext

from termagent.harbor_agent import TermAgentHarbor
from termagent.harbor_runtime import PythonRuntime


def make_agent(tmp_path, **kwargs):
    wheels = tmp_path / "wheels"
    wheels.mkdir(exist_ok=True)
    (wheels / "terminal_coding_agent-0.1.0-py3-none-any.whl").write_bytes(b"test wheel")
    (wheels / "certifi-2026.7.22-py3-none-any.whl").write_bytes(b"test dependency")
    return TermAgentHarbor(
        logs_dir=tmp_path / "logs", wheel_dir=str(wheels),
        test_command="python -m pytest -q", **kwargs,
    )


def test_live_adapter_requires_explicit_model(tmp_path):
    with pytest.raises(ValueError, match="explicit model"):
        make_agent(tmp_path)


def test_adapter_install_uses_uploaded_wheels_offline(tmp_path):
    agent = make_agent(tmp_path, provider="fixture")
    environment = AsyncMock()
    environment.exec.side_effect = [
        ExecResult(
            return_code=0,
            stdout='{"executable":"/usr/local/bin/python3.13","version":[3,13,7]}\n',
        ),
        ExecResult(return_code=0, stdout="termagent-runtime-ok\n"),
    ]
    asyncio.run(agent.setup(environment))
    assert environment.upload_dir.await_count == 1
    assert all(call.kwargs["user"] == "root" for call in environment.exec.await_args_list)
    commands = "\n".join(call.kwargs["command"] for call in environment.exec.await_args_list)
    assert "pip" not in commands
    assert "venv" not in commands
    assert environment.exec.await_args_list[-1].kwargs["env"]["PYTHONPATH"].startswith(
        "/opt/termagent-wheels/"
    )
    assert agent.runtime == PythonRuntime("/usr/local/bin/python3.13", (3, 13, 7))
    assert agent.version().startswith("wheel-sha256:")


def test_setup_reports_all_missing_python_candidates(tmp_path):
    agent = make_agent(tmp_path, provider="fixture")
    environment = AsyncMock()
    environment.exec.return_value = ExecResult(return_code=127, stderr="command not found")

    with pytest.raises(RuntimeError, match=r"requires Python 3\.11\+") as error:
        asyncio.run(agent.setup(environment))

    assert environment.exec.await_count == 4
    assert "python3.13" in str(error.value)
    assert "python3.12" in str(error.value)
    assert "python3.11" in str(error.value)
    assert "python3" in str(error.value)


def test_setup_reports_runtime_bundle_import_failure(tmp_path):
    agent = make_agent(tmp_path, provider="fixture")
    environment = AsyncMock()
    environment.exec.side_effect = [
        ExecResult(
            return_code=0,
            stdout='{"executable":"/usr/bin/python3.11","version":[3,11,9]}\n',
        ),
        ExecResult(return_code=1, stderr="No module named termagent"),
    ]

    with pytest.raises(RuntimeError, match="could not be imported") as error:
        asyncio.run(agent.setup(environment))

    assert "No module named termagent" in str(error.value)


def test_run_requires_successful_setup(tmp_path):
    agent = make_agent(tmp_path, provider="fixture")
    environment = AsyncMock()

    with pytest.raises(RuntimeError, match="setup must complete"):
        asyncio.run(agent.run("fix the tests", environment, AgentContext()))

    environment.exec.assert_not_awaited()


def test_prompt_is_uploaded_as_data_and_credentials_are_not_in_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    agent = make_agent(tmp_path, model_name="openai/test-model", controller_recovery=False)
    agent.runtime = PythonRuntime("/usr/local/bin/python3.13", (3, 13, 7))
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
    assert uploaded["strict_completion"] is True
    assert uploaded["max_stagnation_events"] == 2
    assert uploaded["max_discovery_actions"] == 6
    assert "test-only-secret" not in json.dumps(uploaded)
    call = environment.exec.await_args.kwargs
    assert prompt not in call["command"]
    assert "test-only-secret" not in call["command"]
    assert call["env"]["OPENAI_API_KEY"] == "test-only-secret"
    assert call["env"]["PYTHONPATH"].startswith("/opt/termagent-wheels/")
    assert context.n_input_tokens == 20
    assert context.metadata["completed"] is False
    assert context.metadata["max_output_tokens"] == 4096
    assert context.metadata["reasoning_effort"] == "high"
    assert context.metadata["usage_is_complete"] is True
    assert context.metadata["require_changes"] is True
    assert context.metadata["task_planning"] is True
    assert context.metadata["strict_completion"] is True
    assert context.metadata["completion_evidence_passed"] is None
    assert context.metadata["max_stagnation_events"] == 2
    assert context.metadata["max_discovery_actions"] == 6
    assert context.metadata["search_queries"] == []


def test_missing_key_fails_before_agent_process(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent = make_agent(tmp_path, model_name="test-model")
    agent.runtime = PythonRuntime("/usr/local/bin/python3.13", (3, 13, 7))
    environment = AsyncMock()
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(agent.run("fix", environment, AgentContext()))
    environment.exec.assert_not_awaited()
