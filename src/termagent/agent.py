from __future__ import annotations

import json
import sys

from .diagnostics import tests_passed
from .logging import TraceLogger
from .models import AgentConfig, AgentState, ToolCall
from .pricing import estimate_cost_usd
from .provider import build_provider
from .tools import ToolRegistry


class TerminalAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.tools = ToolRegistry(config.repo, config.approval_mode)
        self.test_command = config.test_command.format(python=sys.executable)
        self.provider = build_provider(
            config.provider,
            model=config.model,
            test_command=self.test_command,
            max_retries=config.provider_retries,
        )
        self.logger = TraceLogger(config.log_dir)
        self.tool_names = {spec.name for spec in self.tools.specs()}

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

            validation_error = self._validate_tool_call(call)
            if validation_error:
                state.final_answer = f"Provider selected an invalid tool call: {validation_error}"
                self.logger.write(
                    "invalid_tool_call",
                    {"step": step, "name": call.name, "arguments": call.arguments, "error": validation_error},
                )
                break

            self.logger.write("tool_call", {"step": step, "name": call.name, "arguments": call.arguments})
            result = self.tools.call(call.name, call.arguments)
            self.logger.write(
                "tool_result",
                {"step": step, "status": result.status, "output": result.output, "metadata": result.metadata},
            )
            observations.append(
                f"{call.name}: {result.status}\nmetadata: {json.dumps(result.metadata, sort_keys=True)}\n{result.output}"
            )
            if result.status == "blocked":
                state.final_answer = (
                    f"Blocked by safety policy while running `{call.name}`.\n\n"
                    f"{result.output}\n\n"
                    "Review the command and rerun with `--approval-mode auto` if it is expected."
                )
                break
            if call.name == "run_shell" and result.status == "ok" and tests_passed(result.output):
                state.tests_passed = True

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
        cost_line = ""
        if state.input_tokens or state.output_tokens:
            cost_line = (
                f"\nTokens: {state.input_tokens} input, {state.output_tokens} output."
                f"\nEstimated model cost: ${state.estimated_cost_usd:.6f}."
            )
        return f"Completed in {state.steps} steps. Tests: {test_status}.{cost_line}\n\nFinal diff:\n{diff}"

    def _validate_tool_call(self, call: ToolCall) -> str | None:
        if call.name not in self.tool_names:
            return f"unknown tool `{call.name}`"
        if not isinstance(call.arguments, dict):
            return "arguments must be a JSON object"
        required_args = {
            "search": {"query"},
            "read_file": {"path"},
            "write_file": {"path", "content"},
            "run_shell": {"command"},
            "git_diff": set(),
        }[call.name]
        missing = sorted(name for name in required_args if name not in call.arguments)
        if missing:
            return f"missing required argument(s): {', '.join(missing)}"
        return None
