"""Harbor 0.22.0 adapter. Install the optional harbor extra on Python 3.12+."""

from __future__ import annotations

import hashlib
import json
import math
import shlex
import tempfile
from pathlib import Path, PurePosixPath

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class TermAgentHarbor(BaseAgent):
    def __init__(
        self,
        *args,
        wheel_dir: str,
        test_command: str,
        repo: str = "/workspace",
        provider: str = "openai",
        max_steps: int = 24,
        max_cost_usd: float = 0.05,
        prompt_profile: str = "conservative",
        controller_recovery: bool = True,
        max_output_tokens: int = 4_096,
        reasoning_effort: str = "high",
        require_changes: bool = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.wheel_dir = Path(wheel_dir).resolve()
        wheels = list(self.wheel_dir.glob("terminal_coding_agent-*.whl"))
        if len(wheels) != 1:
            raise ValueError("wheel_dir must contain exactly one built TermAgent wheel and its dependencies")
        if provider not in {"openai", "repair", "mock"}:
            raise ValueError("unsupported provider")
        if provider == "openai" and not self.model_name:
            raise ValueError("live evaluation requires an explicit model")
        if self.model_name and "/" in self.model_name and not self.model_name.startswith("openai/"):
            raise ValueError("this adapter currently supports OpenAI model IDs only")
        if not isinstance(controller_recovery, bool) or not isinstance(require_changes, bool):
            raise TypeError("controller_recovery and require_changes must be booleans")
        if not PurePosixPath(repo).is_absolute() or not test_command.strip():
            raise ValueError("an absolute container repo and a visible verifier command are required")
        if max_steps < 1 or not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
            raise ValueError("step and cost limits must be positive and finite")
        if prompt_profile not in {"conservative", "benchmark", "fast"}:
            raise ValueError("unsupported prompt profile")
        if max_output_tokens < 256:
            raise ValueError("max_output_tokens must be at least 256")
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError("unsupported reasoning effort")
        self.wheel_hash = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
        self.settings = {
            "repo": repo,
            "provider": provider,
            "model": (self.model_name or "gpt-5.6-luna").removeprefix("openai/"),
            "test_command": test_command,
            "max_steps": max_steps,
            "max_cost_usd": max_cost_usd,
            "prompt_profile": prompt_profile,
            "controller_recovery": controller_recovery,
            "max_output_tokens": max_output_tokens,
            "reasoning_effort": reasoning_effort,
            "require_changes": require_changes,
            "approval_mode": "auto",
        }

    @staticmethod
    def name() -> str:
        return "termagent"

    def version(self) -> str:
        return f"wheel-sha256:{self.wheel_hash}"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.upload_dir(self.wheel_dir, "/opt/termagent-wheels")
        commands = [
            "python3 -m venv --system-site-packages /opt/termagent-venv",
            "/opt/termagent-venv/bin/python -m pip install --no-index --find-links /opt/termagent-wheels terminal-coding-agent",
        ]
        for command in commands:
            result = await environment.exec(command=command, user="root", timeout_sec=120)
            if result.return_code != 0:
                raise RuntimeError("TermAgent installation failed; task image needs Python 3.12+ with venv and pip")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        logs = self.environment_logs_dir
        settings = {**self.settings, "task": instruction, "log_dir": str(logs / "traces")}
        with tempfile.TemporaryDirectory(prefix="termagent-harbor-config-") as temp:
            config = Path(temp) / "config.json"
            config.write_text(json.dumps(settings))
            await environment.upload_file(config, str(logs / "config.json"))
        env = {}
        if self.settings["provider"] == "openai":
            key = self._get_env("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY is required for live Harbor trials")
            env["OPENAI_API_KEY"] = key
        result = await environment.exec(
            command=shlex.join([
                "/opt/termagent-venv/bin/python", "-m", "termagent.harbor_runner",
                "--config", str(logs / "config.json"),
            ]),
            cwd=self.settings["repo"], env=env,
        )
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "stdout.txt").write_text(result.stdout or "")
        (self.logs_dir / "stderr.txt").write_text(result.stderr or "")
        # Incomplete agent runs are graded as trials, not discarded as setup errors.
        if result.return_code not in {0, 1}:
            raise RuntimeError(f"TermAgent process failed with exit code {result.return_code}")
        await environment.download_file(str(logs / "summary.json"), self.logs_dir / "summary.json")
        self.populate_context_post_run(context)

    def populate_context_post_run(self, context: AgentContext) -> None:
        summary = self.logs_dir / "summary.json"
        if not summary.exists():
            return
        state = json.loads(summary.read_text())
        context.n_input_tokens = state["input_tokens"]
        context.n_output_tokens = state["output_tokens"]
        context.cost_usd = state["estimated_cost_usd"]
        context.metadata = {
            "completed": state["completed"],
            "tests_passed": state["tests_passed"],
            "steps": state["steps"],
            "wheel_sha256": self.wheel_hash,
            "cost_is_estimate": True,
            "controller_recovery": self.settings["controller_recovery"],
            "prompt_profile": self.settings["prompt_profile"],
            "max_output_tokens": self.settings["max_output_tokens"],
            "reasoning_effort": self.settings["reasoning_effort"],
            "usage_is_complete": state["usage_is_complete"],
            "require_changes": self.settings["require_changes"],
        }
