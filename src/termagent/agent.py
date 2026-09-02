from __future__ import annotations

from .logging import TraceLogger
from .models import AgentConfig, AgentState
from .provider import build_provider
from .tools import ToolRegistry


class TerminalAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.tools = ToolRegistry(config.repo, config.approval_mode)
        self.provider = build_provider(config.provider)
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
            observations.append(f"{call.name}: {result.status}\n{result.output}")

            if call.name == "git_diff" and result.status == "ok":
                state.completed = True
                state.final_answer = result.output
                break

        if not state.final_answer:
            state.final_answer = observations[-1] if observations else "No actions were taken."

        self.logger.write("agent_finish", {"completed": state.completed, "steps": state.steps})
        return state

