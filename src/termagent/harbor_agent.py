"""Harbor 0.22.0 adapter. Install the optional harbor extra on Python 3.12+."""

from __future__ import annotations

import json
import math
import shlex
import tempfile
from pathlib import Path, PurePosixPath

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .harbor_runtime import (
    PYTHON_CANDIDATES,
    PythonRuntime,
    format_probe_failure,
    load_runtime_bundle,
    parse_python_probe,
    python_bootstrap_command,
    python_probe_command,
    runtime_environment,
    runtime_metadata,
    runtime_validation_command,
)


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
        task_planning: bool = True,
        strict_completion: bool | None = None,
        bootstrap_python: bool = True,
        max_stagnation_events: int = 2,
        max_discovery_actions: int = 6,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.wheel_dir = Path(wheel_dir).resolve()
        self.runtime_bundle = load_runtime_bundle(self.wheel_dir)
        self.runtime: PythonRuntime | None = None
        if provider not in {"openai", "fixture", "repair", "mock"}:
            raise ValueError("unsupported provider")
        if provider == "openai" and not self.model_name:
            raise ValueError("live evaluation requires an explicit model")
        if self.model_name and "/" in self.model_name and not self.model_name.startswith("openai/"):
            raise ValueError("this adapter currently supports OpenAI model IDs only")
        if not all(isinstance(value, bool) for value in (controller_recovery, require_changes, task_planning)):
            raise TypeError("controller_recovery, require_changes, and task_planning must be booleans")
        if strict_completion is not None and not isinstance(strict_completion, bool):
            raise TypeError("strict_completion must be a boolean when provided")
        if not isinstance(bootstrap_python, bool):
            raise TypeError("bootstrap_python must be a boolean")
        resolved_strict_completion = task_planning if strict_completion is None else strict_completion
        if resolved_strict_completion and not task_planning:
            raise ValueError("strict completion requires task planning")
        if not PurePosixPath(repo).is_absolute() or not test_command.strip():
            raise ValueError("an absolute container repo and a visible verifier command are required")
        if max_steps < 1 or not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
            raise ValueError("step and cost limits must be positive and finite")
        if max_stagnation_events < 1:
            raise ValueError("max_stagnation_events must be at least 1")
        if max_discovery_actions < 1:
            raise ValueError("max_discovery_actions must be at least 1")
        if prompt_profile not in {"conservative", "benchmark", "fast"}:
            raise ValueError("unsupported prompt profile")
        if max_output_tokens < 256:
            raise ValueError("max_output_tokens must be at least 256")
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError("unsupported reasoning effort")
        self.wheel_hash = self.runtime_bundle.termagent_sha256
        self.bootstrap_python = bootstrap_python
        self.runtime_bootstrapped = False
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
            "task_planning": task_planning,
            "strict_completion": resolved_strict_completion,
            "max_stagnation_events": max_stagnation_events,
            "max_discovery_actions": max_discovery_actions,
            "approval_mode": "auto",
        }

    @staticmethod
    def name() -> str:
        return "termagent"

    def version(self) -> str:
        return f"wheel-sha256:{self.wheel_hash}"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.upload_dir(self.wheel_dir, "/opt/termagent-wheels")
        failures = await self._probe_python(environment)
        if self.runtime is None and self.bootstrap_python:
            bootstrap = await environment.exec(
                command=python_bootstrap_command(), user="root", timeout_sec=300,
            )
            if bootstrap.return_code == 0:
                self.runtime_bootstrapped = True
                failures.extend(await self._probe_python(environment))
            else:
                detail = " ".join((bootstrap.stdout or bootstrap.stderr or "no output").split())[:300]
                failures.append(
                    f"Python bootstrap failed with exit {bootstrap.return_code}: {detail}"
                )

        if self.runtime is None:
            detail = "; ".join(failures)
            raise RuntimeError(
                "TermAgent requires Python 3.11+ in the task container; "
                f"interpreter probes failed: {detail}"
            )

        validation = await environment.exec(
            command=runtime_validation_command(self.runtime),
            user="root",
            env=runtime_environment(self.runtime_bundle),
            timeout_sec=30,
        )
        if validation.return_code != 0:
            detail = " ".join((validation.stdout or validation.stderr or "no output").split())[:300]
            raise RuntimeError(
                "TermAgent wheel bundle could not be imported in the task container: " + detail
            )

    async def _probe_python(self, environment: BaseEnvironment) -> list[str]:
        failures: list[str] = []
        for candidate in PYTHON_CANDIDATES:
            result = await environment.exec(
                command=python_probe_command(candidate), user="root", timeout_sec=20,
            )
            if result.return_code != 0:
                failures.append(
                    format_probe_failure(candidate, result.return_code, result.stdout or result.stderr or "")
                )
                continue
            try:
                self.runtime = parse_python_probe(result.stdout or "")
                break
            except ValueError as exc:
                failures.append(f"{candidate} (invalid probe: {exc})")
        return failures

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        if self.runtime is None:
            raise RuntimeError("TermAgent Harbor setup must complete before run")
        logs = self.environment_logs_dir
        settings = {**self.settings, "task": instruction, "log_dir": str(logs / "traces")}
        with tempfile.TemporaryDirectory(prefix="termagent-harbor-config-") as temp:
            config = Path(temp) / "config.json"
            config.write_text(json.dumps(settings))
            await environment.upload_file(config, str(logs / "config.json"))
        extra_env = {}
        if self.settings["provider"] == "openai":
            key = self._get_env("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY is required for live Harbor trials")
            extra_env["OPENAI_API_KEY"] = key
        env = runtime_environment(self.runtime_bundle, extra_env)
        result = await environment.exec(
            command=shlex.join([
                self.runtime.executable, "-m", "termagent.harbor_runner",
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
            **runtime_metadata(self.runtime_bundle, self.runtime),
            "cost_is_estimate": True,
            "controller_recovery": self.settings["controller_recovery"],
            "prompt_profile": self.settings["prompt_profile"],
            "max_output_tokens": self.settings["max_output_tokens"],
            "reasoning_effort": self.settings["reasoning_effort"],
            "usage_is_complete": state["usage_is_complete"],
            "require_changes": self.settings["require_changes"],
            "task_planning": self.settings["task_planning"],
            "strict_completion": self.settings["strict_completion"],
            "bootstrap_python": self.bootstrap_python,
            "runtime_bootstrapped": self.runtime_bootstrapped,
            "completion_reviewed": state.get("completion_reviewed"),
            "completion_evidence_passed": state.get("completion_evidence_passed"),
            "completion_blockers": state.get("completion_blockers", []),
            "completion_checks": state.get("completion_checks", []),
            "diff_paths": state.get("diff_paths", []),
            "verifier_strength": state.get("verifier_strength"),
            "phase": state.get("phase"),
            "stagnation_events": state.get("stagnation_events"),
            "max_stagnation_events": self.settings["max_stagnation_events"],
            "max_discovery_actions": self.settings["max_discovery_actions"],
            "discovery_actions": state.get("discovery_actions"),
            "transition_events": state.get("transition_events"),
            "inspected_paths": state.get("inspected_paths", []),
            "inspected_symbols": state.get("inspected_symbols", []),
            "search_queries": state.get("search_queries", []),
        }
