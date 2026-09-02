from __future__ import annotations

import json
import sys

from .diagnostics import tests_passed
from .logging import TraceLogger
from .models import AgentConfig, AgentState
from .provider import build_provider
from .tools import ToolRegistry


class TerminalAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.tools = ToolRegistry(config.repo, config.approval_mode)
        self.test_command = config.test_command.format(python=sys.executable)
        self.provider = build_provider(config.provider, test_command=self.test_command)
        self.logger = TraceLogger(config.log_dir)

    def run(self) -> AgentState:
        state = AgentState()
        observations: list[str] = []
        self.logger.write(
            "agent_start",
            {
                "repo": str(self.config.repo),
                "task": self.config.task,
                "provider": self.config.provider,
                "approval_mode": self.config.approval_mode,
                "test_command": self.test_command,
            },
        )

        for step in range(1, self.config.max_steps + 1):
            state.steps = step
            call = self.provider.next_action(self.config.task, observations)
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
                state.final_answer = self._format_final_answer(state.steps, state.tests_passed, result.output)
                break

        if not state.final_answer:
            state.final_answer = observations[-1] if observations else "No actions were taken."

        self.logger.write("agent_finish", {"completed": state.completed, "steps": state.steps})
        return state

    @staticmethod
    def _format_final_answer(steps: int, passed: bool, diff: str) -> str:
        status = "passed" if passed else "not confirmed"
        return f"Completed in {steps} steps. Tests: {status}.\n\nFinal diff:\n{diff}"
