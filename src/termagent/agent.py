from __future__ import annotations

import json
import shlex
import sys

from .diagnostics import parse_pytest_failure
from .logging import TraceLogger
from .models import AgentConfig, AgentState, TokenUsage, ToolCall
from .planning import ProgressLedger
from .pricing import estimate_cost_usd
from .provider import (
    ProviderError,
    build_provider,
    first_code_map_symbol_path,
    first_search_path,
)
from .safety import resolve_inside_root
from .tools import ToolRegistry, sha256_text


class TerminalAgent:
    def __init__(self, config: AgentConfig) -> None:
        if config.max_stagnation_events < 1:
            raise ValueError("max_stagnation_events must be at least 1")
        self.config = config
        self.tools = ToolRegistry(
            config.repo,
            config.approval_mode,
            allow_network=config.allow_network_commands,
        )
        self.test_command = config.test_command.format(python=shlex.quote(sys.executable))
        self.provider = build_provider(
            config.provider,
            model=config.model,
            test_command=self.test_command,
            max_retries=config.provider_retries,
            prompt_profile=config.prompt_profile,
            observation_limit=config.observation_limit,
            max_observation_chars=config.max_observation_chars,
            max_output_tokens=config.max_output_tokens,
            reasoning_effort=config.reasoning_effort,
            task_planning=config.task_planning,
        )
        self.logger = TraceLogger(config.log_dir)
        self.tool_names = {spec.name for spec in self.tools.specs()}
        self.planned_writes: set[tuple[str, str]] = set()
        self.progress = ProgressLedger(enabled=config.task_planning)

    def run(self) -> AgentState:
        state = AgentState()
        observations: list[str] = []
        last_failed_test_command: str | None = None
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
                "controller_recovery": self.config.controller_recovery,
                "max_output_tokens": self.config.max_output_tokens,
                "reasoning_effort": self.config.reasoning_effort,
                "require_changes": self.config.require_changes,
                "task_planning": self.config.task_planning,
                "max_stagnation_events": self.config.max_stagnation_events,
            },
        )

        for step in range(1, self.config.max_steps + 1):
            state.steps = step
            try:
                provider_output = self.provider.next_action(self.config.task, observations)
            except ProviderError as exc:
                self._record_usage(state, exc.usage)
                state.usage_is_complete = exc.usage_is_complete
                state.final_answer = f"Provider error: {exc}"
                self.logger.write("provider_error", {
                    "step": step,
                    "error": str(exc),
                    "attempts": exc.attempts,
                    "input_tokens": exc.usage.input_tokens,
                    "output_tokens": exc.usage.output_tokens,
                    "usage_is_complete": exc.usage_is_complete,
                })
                break
            except RuntimeError as exc:
                state.usage_is_complete = False
                state.final_answer = f"Provider error: {exc}"
                self.logger.write(
                    "provider_error", {"step": step, "error": str(exc), "usage_is_complete": False}
                )
                break

            call = normalize_tool_call(provider_output.tool_call)
            controller_call = (
                self._controller_redirect(
                    call, observations, last_failed_test_command, state.tests_passed,
                )
                if self.config.controller_recovery else None
            )
            if controller_call:
                self.logger.write(
                    "controller_redirect",
                    {
                        "step": step,
                        "from": {"name": call.name, "arguments": call.arguments},
                        "to": {"name": controller_call.name, "arguments": controller_call.arguments},
                    },
                )
                call = controller_call
            self._record_usage(state, provider_output.usage)
            state.usage_is_complete = (
                state.usage_is_complete and provider_output.usage_is_complete
            )
            self.logger.write(
                "provider_usage",
                {
                    "step": step,
                    "attempts": provider_output.attempts,
                    "input_tokens": provider_output.usage.input_tokens,
                    "output_tokens": provider_output.usage.output_tokens,
                    "estimated_cost_usd": state.estimated_cost_usd,
                    "usage_is_complete": provider_output.usage_is_complete,
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

            if self.config.task_planning and self.progress.record_proposal(call):
                self.progress.stagnation_events += 1
                state.stagnation_events = self.progress.stagnation_events
                guidance = self._stagnation_guidance(call)
                observations.append(
                    "controller_stagnation: blocked\n"
                    f"metadata: {json.dumps({'repeated_tool': call.name, 'phase': self.progress.phase}, sort_keys=True)}\n"
                    f"{guidance}"
                )
                self.logger.write(
                    "stagnation_detected",
                    {
                        "step": step,
                        "tool": call.name,
                        "phase": self.progress.phase,
                        "events": self.progress.stagnation_events,
                    },
                )
                if self.progress.stagnation_events >= self.config.max_stagnation_events:
                    state.final_answer = (
                        "Stopped after repeated no-progress tool selections. "
                        f"Last blocked tool: `{call.name}`. {guidance}"
                    )
                    break
                continue

            self.logger.write("tool_call", {"step": step, "name": call.name, "arguments": call.arguments})
            # Commands and writes may change files, even when they fail partway through.
            if call.name in {"write_file", "write_patch_set", "run_shell"}:
                state.tests_passed = False
            result = self.tools.call(call.name, call.arguments)
            self.logger.write(
                "tool_result",
                {"step": step, "status": result.status, "output": result.output, "metadata": result.metadata},
            )
            observations.append(
                f"{call.name}: {result.status}\nmetadata: {json.dumps(result.metadata, sort_keys=True)}\n{result.output}"
            )
            if call.name == "set_task_plan" and result.status == "ok":
                self.progress.register_plan(result.metadata)
                if self.progress.plan is not None:
                    state.task_plan_summary = self.progress.plan.summary
                    state.expected_paths = list(self.progress.plan.expected_paths)
                    state.acceptance_checks = list(self.progress.plan.acceptance_checks)
            if call.name == "plan_patch" and result.status == "ok":
                relative_path = result.metadata.get("relative_path")
                content_hash = result.metadata.get("content_sha256")
                if isinstance(relative_path, str) and isinstance(content_hash, str):
                    self.planned_writes.add((relative_path, content_hash))
                    state.patch_plans += 1
                    self.progress.mark_progress("implement")
            if call.name == "plan_patch_set" and result.status == "ok":
                state.patch_plans += self._remember_grouped_plan(result.metadata)
                self.progress.mark_progress("implement")

            if result.status == "blocked":
                state.final_answer = (
                    f"Blocked by safety policy while running `{call.name}`.\n\n"
                    f"{result.output}\n\n"
                    "Review the command and rerun with `--approval-mode auto` if it is expected."
                )
                break
            if call.name == "write_file" and result.status == "ok":
                last_failed_test_command = None
                relative_path = result.metadata.get("relative_path")
                if isinstance(relative_path, str) and relative_path not in state.changed_files:
                    state.changed_files.append(relative_path)
                content_hash = result.metadata.get("content_sha256")
                if isinstance(relative_path, str) and isinstance(content_hash, str):
                    self.planned_writes.discard((relative_path, content_hash))
                self.progress.mark_progress("verify")
            if call.name == "write_patch_set" and result.status == "ok":
                last_failed_test_command = None
                self._record_grouped_write(state, result.metadata)
                self.progress.mark_progress("verify")

            if call.name == "run_shell" and self._is_verifier(call.arguments.get("command")):
                command = call.arguments.get("command", "")
                state.test_runs.append(command)
                passed = result.status == "ok" and result.metadata.get("returncode") == 0
                state.tests_passed = passed
                last_failed_test_command = None if passed else command
                if not passed:
                    state.failed_test_runs += 1
                    observations[-1] += (
                        "\n\ncontroller_guidance: next_action\n"
                        "The verifier failed. Do not rerun the same test command again until after "
                        "a file write. Inspect the relevant code with code_map, find_references, "
                        "search, or read_file, then plan a minimal patch."
                    )
                    self.logger.write(
                        "reflection",
                        {
                            "step": step,
                            "summary": "test command did not pass; continue with targeted diagnosis",
                            "failed_test_runs": state.failed_test_runs,
                        },
                    )
                    self.progress.mark_progress("diagnose")
                else:
                    self.progress.mark_progress("review")

            if call.name == "git_diff" and result.status == "ok":
                if self.config.task_planning and self.progress.plan is None:
                    observations[-1] += (
                        "\n\ncontroller_guidance: task_plan_required\n"
                        "Register the goal, expected output paths, and acceptance checks with "
                        "set_task_plan before finishing."
                    )
                    continue
                missing_paths = self.progress.missing_expected_paths(self.tools.repo)
                if missing_paths:
                    observations[-1] += (
                        "\n\ncontroller_guidance: missing_deliverables\n"
                        "The task plan still has missing expected files: " + ", ".join(missing_paths)
                    )
                    self.progress.phase = "implement"
                    continue
                has_changes = result.output.strip() not in {"", "no diff"}
                if self.config.require_changes and not has_changes:
                    observations[-1] += (
                        "\n\ncontroller_guidance: task_not_complete\n"
                        "This run requires a repository change, but the diff is empty. Inspect the "
                        "task inputs and create or modify the requested files before finishing."
                    )
                    self.logger.write(
                        "reflection",
                        {"step": step, "summary": "task requires a change but the diff is empty"},
                    )
                    continue
                state.completed = state.tests_passed
                self.progress.mark_progress("complete" if state.completed else "review")
                state.phase = self.progress.phase
                state.final_answer = self._format_final_answer(state, result.output)
                break

        if not state.final_answer:
            state.final_answer = observations[-1] if observations else "No actions were taken."

        state.phase = self.progress.phase
        state.stagnation_events = self.progress.stagnation_events
        self.logger.write("agent_finish", {
            "completed": state.completed, "tests_passed": state.tests_passed, "steps": state.steps,
            "phase": state.phase, "stagnation_events": state.stagnation_events,
        })
        return state

    def _is_verifier(self, command: object) -> bool:
        if not isinstance(command, str):
            return False
        try:
            parts = shlex.split(command)
            return bool(parts) and parts == shlex.split(self.test_command)
        except ValueError:
            return False

    @staticmethod
    def _format_final_answer(state: AgentState, diff: str) -> str:
        test_status = "passed" if state.tests_passed else "not confirmed"
        files = ", ".join(state.changed_files) if state.changed_files else "none"
        residual_risk = "only the configured verifier was checked" if state.tests_passed else "tests did not confirm the change"
        subsystems = summarize_subsystems(state.changed_files)
        rollback = rollback_guidance(state.changed_files)
        lines = [
            f"{'Completed' if state.completed else 'Incomplete'} in {state.steps} steps.",
            f"Files changed: {files}.",
            f"Subsystems changed: {subsystems}.",
            f"Patch plans reviewed: {state.patch_plans}.",
            f"Tests run: {len(state.test_runs)}; status: {test_status}.",
            f"Failed test attempts before completion: {state.failed_test_runs}.",
            f"Residual risk: {residual_risk}.",
            f"Rollback guidance: {rollback}.",
        ]
        if state.task_plan_summary:
            lines.insert(1, f"Task plan: {state.task_plan_summary}")
            lines.insert(2, f"Declared outputs: {', '.join(state.expected_paths) or 'discovered during implementation'}.")
        lines.append(f"Progress phase: {state.phase}; stagnation events: {state.stagnation_events}.")
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

    def _record_usage(self, state: AgentState, usage: TokenUsage) -> None:
        state.input_tokens += usage.input_tokens
        state.output_tokens += usage.output_tokens
        state.estimated_cost_usd += estimate_cost_usd(self.config.model, usage)

    def _validate_tool_call(self, call: ToolCall) -> str | None:
        if call.name not in self.tool_names:
            return f"unknown tool `{call.name}`"
        if not isinstance(call.arguments, dict):
            return "arguments must be a JSON object"
        required_args = {
            "set_task_plan": {"summary", "expected_paths", "acceptance_checks"},
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
        allowed_args = {
            "set_task_plan": {"summary", "expected_paths", "acceptance_checks"},
            "search": {"query", "glob"},
            "read_file": {"path", "start", "limit"},
            "code_map": {"query", "limit"},
            "find_references": {"symbol", "limit"},
            "plan_patch": {"path", "content"},
            "plan_patch_set": {"files"},
            "write_file": {"path", "content"},
            "write_patch_set": {"files"},
            "run_shell": {"command", "timeout"},
            "git_diff": set(),
        }[call.name]
        unexpected = sorted(set(call.arguments) - allowed_args)
        if unexpected:
            return f"unexpected argument(s): {', '.join(unexpected)}"
        if call.name == "set_task_plan" and self.progress.plan is not None:
            return "task plan is already registered; continue with the existing plan"
        if (
            call.name == "set_task_plan"
            and self.config.task_planning
            and self.config.require_changes
            and not call.arguments.get("expected_paths")
        ):
            return "planning a required change needs at least one expected output path"
        if (
            self.config.task_planning
            and call.name in {"plan_patch", "plan_patch_set"}
            and self.progress.plan is None
        ):
            return "set_task_plan is required before planning file writes"
        if call.name == "write_file":
            plan_error = self._validate_planned_write(call)
            if plan_error:
                return plan_error
        if call.name == "write_patch_set":
            plan_error = self._validate_planned_write_set(call)
            if plan_error:
                return plan_error
        return None

    def _stagnation_guidance(self, call: ToolCall) -> str:
        if self.progress.plan is None:
            return (
                "Stop repeating discovery. Use set_task_plan to state the requested deliverables; "
                "an empty repository is evidence that explicitly requested files must be created."
            )
        if self.progress.phase in {"plan", "implement"}:
            return "Choose a concrete planned write that advances one declared deliverable."
        if self.progress.phase == "verify":
            return "Run the configured verifier once, then inspect failures or review the diff."
        return f"Choose a different evidence source or action instead of repeating {call.name}."

    def _controller_redirect(
        self,
        call: ToolCall,
        observations: list[str],
        last_failed_test_command: str | None,
        tests_passed: bool,
    ) -> ToolCall | None:
        if not isinstance(call.arguments, dict):
            return None
        if tests_passed and call.name == "run_shell" and self._is_verifier(
            call.arguments.get("command")
        ):
            return ToolCall("git_diff", {})
        if call.name != "run_shell" or not last_failed_test_command:
            return None
        if call.arguments.get("command") != last_failed_test_command:
            return None
        if not observations:
            return None

        latest = observations[-1]
        if latest.startswith("run_shell: ok"):
            failure = parse_pytest_failure(latest)
            if failure.symbol:
                return ToolCall("code_map", {"query": failure.symbol})
            if failure.file_path:
                return ToolCall("read_file", {"path": failure.file_path})
            return ToolCall("code_map", {})

        if latest.startswith("code_map: ok"):
            path = first_code_map_symbol_path(latest)
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("search: ok"):
            path = first_search_path(latest)
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("read_file: error"):
            failure = latest_pytest_failure(observations)
            if failure and failure.symbol:
                return ToolCall("search", {"query": f"def {failure.symbol}", "glob": "*.py"})
            return ToolCall("code_map", {})

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


def normalize_tool_call(call: ToolCall) -> ToolCall:
    if not isinstance(call.arguments, dict):
        return call
    return ToolCall(call.name, {key: value for key, value in call.arguments.items() if value is not None})


def latest_pytest_failure(observations: list[str]):
    for observation in reversed(observations):
        if observation.startswith("run_shell: ok"):
            failure = parse_pytest_failure(observation)
            if failure.file_path or failure.symbol or failure.assertion:
                return failure
    return None


def rollback_guidance(paths: list[str]) -> str:
    if not paths:
        return "no file changes to roll back"
    return "revert the listed files from the final diff if follow-up validation fails"
