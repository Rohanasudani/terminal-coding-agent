from __future__ import annotations

import json
import sys

from .diagnostics import tests_passed
from .logging import TraceLogger
from .models import AgentConfig, AgentState, ToolCall
from .pricing import estimate_cost_usd
from .provider import build_provider
from .safety import resolve_inside_root
from .tools import ToolRegistry, sha256_text


class TerminalAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.tools = ToolRegistry(
            config.repo,
            config.approval_mode,
            allow_network=config.allow_network_commands,
        )
        self.test_command = config.test_command.format(python=sys.executable)
        self.provider = build_provider(
            config.provider,
            model=config.model,
            test_command=self.test_command,
            max_retries=config.provider_retries,
            prompt_profile=config.prompt_profile,
            observation_limit=config.observation_limit,
            max_observation_chars=config.max_observation_chars,
        )
        self.logger = TraceLogger(config.log_dir)
        self.tool_names = {spec.name for spec in self.tools.specs()}
        self.planned_writes: set[tuple[str, str]] = set()

    def run(self) -> AgentState:
        state = AgentState()
        observations: list[str] = []
        self.logger.write(
            "agent_start",
            {
                "repo": str(self.config.repo),
                "task": self.config.task,
                "provider": self.config.provider,
                "model": self.config.model,
                    "approval_mode": self.config.approval_mode,
                    "test_command": self.test_command,
                    "prompt_profile": self.config.prompt_profile,
                    "max_cost_usd": self.config.max_cost_usd,
                    "allow_network_commands": self.config.allow_network_commands,
                },
            )

        for step in range(1, self.config.max_steps + 1):
            state.steps = step
            try:
                provider_output = self.provider.next_action(self.config.task, observations)
            except RuntimeError as exc:
                state.final_answer = f"Provider error: {exc}"
                self.logger.write("provider_error", {"step": step, "error": str(exc)})
                break

            call = provider_output.tool_call
            state.input_tokens += provider_output.usage.input_tokens
            state.output_tokens += provider_output.usage.output_tokens
            state.estimated_cost_usd = estimate_cost_usd(
                self.config.model,
                provider_output.usage,
            ) + state.estimated_cost_usd
            self.logger.write(
                "provider_usage",
                {
                    "step": step,
                    "attempts": provider_output.attempts,
                    "input_tokens": provider_output.usage.input_tokens,
                    "output_tokens": provider_output.usage.output_tokens,
                    "estimated_cost_usd": state.estimated_cost_usd,
                },
            )
            if self._cost_limit_exceeded(state):
                state.stopped_by_cost_limit = True
                state.final_answer = (
                    f"Stopped before executing `{provider_output.tool_call.name}` because the run exceeded "
                    f"the configured model cost ceiling of ${self.config.max_cost_usd:.6f}. "
                    f"Estimated cost so far: ${state.estimated_cost_usd:.6f}."
                )
                self.logger.write(
                    "cost_limit_exceeded",
                    {
                        "step": step,
                        "estimated_cost_usd": state.estimated_cost_usd,
                        "max_cost_usd": self.config.max_cost_usd,
                    },
                )
                break

            validation_error = self._validate_tool_call(call)
            if validation_error:
                state.validation_errors += 1
                self.logger.write(
                    "invalid_tool_call",
                    {
                        "step": step,
                        "name": call.name,
                        "arguments": call.arguments,
                        "error": validation_error,
                        "validation_errors": state.validation_errors,
                    },
                )
                observations.append(
                    "tool_validation: error\n"
                    f"metadata: {json.dumps({'name': call.name, 'arguments': call.arguments}, sort_keys=True)}\n"
                    f"{validation_error}"
                )
                if state.validation_errors >= self.config.max_validation_errors:
                    state.final_answer = (
                        "Provider selected invalid tool calls repeatedly: "
                        f"{validation_error}"
                    )
                    break
                continue

            self.logger.write("tool_call", {"step": step, "name": call.name, "arguments": call.arguments})
            result = self.tools.call(call.name, call.arguments)
            self.logger.write(
                "tool_result",
                {"step": step, "status": result.status, "output": result.output, "metadata": result.metadata},
            )
            observations.append(
                f"{call.name}: {result.status}\nmetadata: {json.dumps(result.metadata, sort_keys=True)}\n{result.output}"
            )
            if call.name == "plan_patch" and result.status == "ok":
                relative_path = result.metadata.get("relative_path")
                content_hash = result.metadata.get("content_sha256")
                if isinstance(relative_path, str) and isinstance(content_hash, str):
                    self.planned_writes.add((relative_path, content_hash))
                    state.patch_plans += 1
            if call.name == "plan_patch_set" and result.status == "ok":
                state.patch_plans += self._remember_grouped_plan(result.metadata)

            if result.status == "blocked":
                state.final_answer = (
                    f"Blocked by safety policy while running `{call.name}`.\n\n"
                    f"{result.output}\n\n"
                    "Review the command and rerun with `--approval-mode auto` if it is expected."
                )
                break
            if call.name == "write_file" and result.status == "ok":
                relative_path = result.metadata.get("relative_path")
                if isinstance(relative_path, str) and relative_path not in state.changed_files:
                    state.changed_files.append(relative_path)
                content_hash = result.metadata.get("content_sha256")
                if isinstance(relative_path, str) and isinstance(content_hash, str):
                    self.planned_writes.discard((relative_path, content_hash))
            if call.name == "write_patch_set" and result.status == "ok":
                self._record_grouped_write(state, result.metadata)

            if call.name == "run_shell" and result.status == "ok":
                command = call.arguments.get("command", "")
                if isinstance(command, str):
                    state.test_runs.append(command)
                passed = tests_passed(result.output)
                state.tests_passed = state.tests_passed or passed
                if not passed:
                    state.failed_test_runs += 1
                    self.logger.write(
                        "reflection",
                        {
                            "step": step,
                            "summary": "test command did not pass; continue with targeted diagnosis",
                            "failed_test_runs": state.failed_test_runs,
                        },
                    )

            if call.name == "git_diff" and result.status == "ok":
                state.completed = True
                state.final_answer = self._format_final_answer(state, result.output)
                break

        if not state.final_answer:
            state.final_answer = observations[-1] if observations else "No actions were taken."

        self.logger.write("agent_finish", {"completed": state.completed, "steps": state.steps})
        return state

    @staticmethod
    def _format_final_answer(state: AgentState, diff: str) -> str:
        test_status = "passed" if state.tests_passed else "not confirmed"
        files = ", ".join(state.changed_files) if state.changed_files else "none"
        residual_risk = "none known" if state.tests_passed else "tests did not confirm the change"
        subsystems = summarize_subsystems(state.changed_files)
        rollback = rollback_guidance(state.changed_files)
        lines = [
            f"Completed in {state.steps} steps.",
            f"Files changed: {files}.",
            f"Subsystems changed: {subsystems}.",
            f"Patch plans reviewed: {state.patch_plans}.",
            f"Tests run: {len(state.test_runs)}; status: {test_status}.",
            f"Failed test attempts before completion: {state.failed_test_runs}.",
            f"Residual risk: {residual_risk}.",
            f"Rollback guidance: {rollback}.",
        ]
        if state.input_tokens or state.output_tokens:
            lines.append(
                f"Tokens: {state.input_tokens} input, {state.output_tokens} output; "
                f"estimated model cost: ${state.estimated_cost_usd:.6f}."
            )
        return "\n".join(lines) + f"\n\nFinal diff:\n{diff}"

    def _cost_limit_exceeded(self, state: AgentState) -> bool:
        if self.config.max_cost_usd is None:
            return False
        return state.estimated_cost_usd > self.config.max_cost_usd

    def _validate_tool_call(self, call: ToolCall) -> str | None:
        if call.name not in self.tool_names:
            return f"unknown tool `{call.name}`"
        if not isinstance(call.arguments, dict):
            return "arguments must be a JSON object"
        required_args = {
            "search": {"query"},
            "read_file": {"path"},
            "code_map": set(),
            "find_references": {"symbol"},
            "plan_patch": {"path", "content"},
            "plan_patch_set": {"files"},
            "write_file": {"path", "content"},
            "write_patch_set": {"files"},
            "run_shell": {"command"},
            "git_diff": set(),
        }[call.name]
        missing = sorted(name for name in required_args if name not in call.arguments)
        if missing:
            return f"missing required argument(s): {', '.join(missing)}"
        if call.name == "write_file":
            plan_error = self._validate_planned_write(call)
            if plan_error:
                return plan_error
        if call.name == "write_patch_set":
            plan_error = self._validate_planned_write_set(call)
            if plan_error:
                return plan_error
        return None

    def _validate_planned_write(self, call: ToolCall) -> str | None:
        path = str(call.arguments.get("path", ""))
        content = str(call.arguments.get("content", ""))
        try:
            target = resolve_inside_root(self.tools.repo, path)
        except ValueError as exc:
            return str(exc)

        relative_path = str(target.relative_to(self.tools.repo))
        planned_key = (relative_path, sha256_text(content))
        if planned_key not in self.planned_writes:
            return "write_file requires a matching plan_patch first"
        return None

    def _validate_planned_write_set(self, call: ToolCall) -> str | None:
        files = call.arguments.get("files")
        if not isinstance(files, list) or not files:
            return "write_patch_set requires a non-empty files list"

        for item in files:
            if not isinstance(item, dict):
                return "write_patch_set files must be objects"
            path = item.get("path")
            content = item.get("content")
            if not isinstance(path, str) or not isinstance(content, str):
                return "write_patch_set files require path and content strings"
            try:
                target = resolve_inside_root(self.tools.repo, path)
            except ValueError as exc:
                return str(exc)
            relative_path = str(target.relative_to(self.tools.repo))
            if (relative_path, sha256_text(content)) not in self.planned_writes:
                return "write_patch_set requires a matching plan_patch_set first"
        return None

    def _remember_grouped_plan(self, metadata: dict[str, object]) -> int:
        files = metadata.get("files")
        if not isinstance(files, list):
            return 0

        count = 0
        for item in files:
            if not isinstance(item, dict):
                continue
            relative_path = item.get("relative_path")
            content_hash = item.get("content_sha256")
            if isinstance(relative_path, str) and isinstance(content_hash, str):
                self.planned_writes.add((relative_path, content_hash))
                count += 1
        return count

    def _record_grouped_write(self, state: AgentState, metadata: dict[str, object]) -> None:
        files = metadata.get("files")
        if not isinstance(files, list):
            return

        for item in files:
            if not isinstance(item, dict):
                continue
            relative_path = item.get("relative_path")
            content_hash = item.get("content_sha256")
            if isinstance(relative_path, str) and relative_path not in state.changed_files:
                state.changed_files.append(relative_path)
            if isinstance(relative_path, str) and isinstance(content_hash, str):
                self.planned_writes.discard((relative_path, content_hash))


def summarize_subsystems(paths: list[str]) -> str:
    if not paths:
        return "none"
    subsystems = sorted({path.split("/", maxsplit=1)[0] if "/" in path else "root" for path in paths})
    return ", ".join(subsystems)


def rollback_guidance(paths: list[str]) -> str:
    if not paths:
        return "no file changes to roll back"
    return "revert the listed files from the final diff if follow-up validation fails"
