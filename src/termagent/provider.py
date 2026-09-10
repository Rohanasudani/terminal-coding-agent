from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import certifi

from .diagnostics import parse_pytest_failure, tests_passed
from .models import PromptProfile, ProviderOutput, ReasoningEffort, TokenUsage, ToolCall


class Provider(ABC):
    @abstractmethod
    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        raise NotImplementedError


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        usage: TokenUsage | None = None,
        attempts: int = 0,
        usage_is_complete: bool = False,
    ) -> None:
        super().__init__(message)
        self.usage = usage or TokenUsage()
        self.attempts = attempts
        self.usage_is_complete = usage_is_complete


class ProviderRequestError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class RepairProvider(Provider):
    """A deterministic test-first repair loop for benchmarks and demos."""

    test_command: str = f"{sys.executable} -m pytest -q"
    task_planning: bool = False
    pending_patch: dict[str, str] | None = field(default=None, init=False)
    pending_patch_set: list[dict[str, str]] | None = field(default=None, init=False)
    pending_action_after_plan: ToolCall | None = field(default=None, init=False)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return ProviderOutput(self._choose_tool(task, observations))

    def _choose_tool(self, task: str, observations: list[str]) -> ToolCall:
        joined = "\n".join(observations).lower()
        latest = observations[-1].lower() if observations else ""

        if not observations:
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("set_task_plan: ok") and self.pending_action_after_plan:
            action = self.pending_action_after_plan
            self.pending_action_after_plan = None
            return action

        if latest.startswith("run_shell: ok") and tests_passed(latest):
            return ToolCall("git_diff", {})

        patch_set = patch_set_from_task(task)
        if latest.startswith("run_shell: ok") and patch_set:
            self.pending_patch_set = patch_set
            return self._with_task_plan(
                task,
                ToolCall("plan_patch_set", {"files": patch_set}),
                [item["path"] for item in patch_set],
            )

        if latest.startswith("run_shell: ok"):
            failure = parse_pytest_failure(observations[-1])
            if failure.symbol:
                return ToolCall("code_map", {"query": failure.symbol})
            if failure.file_path:
                return ToolCall("read_file", {"path": failure.file_path})
            task_symbol = symbol_from_task(task)
            if task_symbol:
                return ToolCall("code_map", {"query": task_symbol})
            return ToolCall("code_map", {})

        if "calculator.py" in joined and "read_file" not in joined:
            return ToolCall("read_file", {"path": "calculator.py"})

        if latest.startswith("search: ok"):
            path = first_search_path(observations[-1])
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("code_map: ok"):
            path = first_code_map_symbol_path(observations[-1])
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("write_file: ok"):
            self.pending_patch = None
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("write_patch_set: ok"):
            self.pending_patch_set = None
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("plan_patch: ok") and self.pending_patch:
            return ToolCall("write_file", self.pending_patch)

        if latest.startswith("plan_patch_set: ok") and self.pending_patch_set:
            return ToolCall("write_patch_set", {"files": self.pending_patch_set})

        if latest.startswith("read_file: ok"):
            imported_symbol = symbol_imported_by_test(observations[-1])
            if imported_symbol:
                return ToolCall("search", {"query": f"def {imported_symbol}", "glob": "*.py"})
            patch = patch_from_read_output(task, observations[-1])
            if patch:
                self.pending_patch = patch
                return self._with_task_plan(
                    task,
                    ToolCall("plan_patch", patch),
                    [patch["path"]],
                )

        return ToolCall("git_diff", {})

    def _with_task_plan(self, task: str, action: ToolCall, expected_paths: list[str]) -> ToolCall:
        if not self.task_planning:
            return action
        self.pending_action_after_plan = action
        return ToolCall(
            "set_task_plan",
            {
                "summary": task.strip() or "Complete the requested repository change",
                "expected_paths": expected_paths,
                "acceptance_checks": [f"The configured verifier passes: {self.test_command}"],
            },
        )


@dataclass
class MockProvider(Provider):
    """Deterministic provider for local tests and demos."""

    repair: RepairProvider = field(default_factory=RepairProvider)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return self.repair.next_action(task, observations)


class OpenAICompatibleProvider(Provider):
    def __init__(
        self,
        model: str,
        test_command: str | None = None,
        max_retries: int = 2,
        prompt_profile: PromptProfile = "conservative",
        observation_limit: int = 6,
        max_observation_chars: int = 8_000,
        max_output_tokens: int = 4_096,
        reasoning_effort: ReasoningEffort | None = None,
        task_planning: bool = False,
    ) -> None:
        self.model = model
        self.test_command = test_command
        self.max_retries = max(0, max_retries)
        self.prompt_profile = prompt_profile
        self.observation_limit = max(1, observation_limit)
        self.max_observation_chars = max(1_000, max_observation_chars)
        if max_output_tokens < 256:
            raise ValueError("max_output_tokens must be at least 256")
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self.task_planning = task_planning
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        invalid_outputs: list[str] = []
        usage = TokenUsage()
        usage_is_complete = True

        for attempt in range(1, self.max_retries + 2):
            payload = self._payload(task, observations, invalid_outputs)
            try:
                data = self._request(payload)
            except ProviderRequestError as exc:
                usage_is_complete = False
                if exc.retryable and attempt <= self.max_retries:
                    time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
                    continue
                raise ProviderError(
                    str(exc),
                    usage=usage,
                    attempts=attempt,
                    usage_is_complete=usage_is_complete,
                ) from exc
            usage = add_usage(usage, usage_from_response(data))
            try:
                call = extract_openai_tool_call(data)
                return ProviderOutput(
                    tool_call=call,
                    usage=usage,
                    attempts=attempt,
                    usage_is_complete=usage_is_complete,
                )
            except (TypeError, ValueError) as exc:
                text = extract_output_text(data)
                invalid_outputs.append(f"{text[:500]}\nerror: {exc}")

        latest_error = invalid_outputs[-1].split("error:", maxsplit=1)[-1].strip() if invalid_outputs else "unknown parser error"
        raise ProviderError(
            f"provider returned invalid tool call after retries: {latest_error}",
            usage=usage,
            attempts=self.max_retries + 1,
            usage_is_complete=usage_is_complete,
        )

    def _payload(self, task: str, observations: list[str], invalid_outputs: list[str]) -> dict[str, object]:
        repair_note = ""
        if invalid_outputs:
            repair_note = "\n\nInvalid previous outputs:\n" + "\n\n".join(invalid_outputs[-2:])

        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": provider_system_prompt(
                        self.prompt_profile, task_planning=self.task_planning,
                    ),
                },
                {
                    "role": "user",
                    "content": f"Task:\n{task}\n\nConfigured verifier command:\n"
                    + (self.test_command or "not configured")
                    + "\n\nObservations:\n"
                    + compact_observations(
                        observations,
                        limit=self.observation_limit,
                        max_chars=self.max_observation_chars,
                    )
                    + repair_note,
                },
            ],
            "tools": openai_tool_definitions(),
            "tool_choice": "required",
            "max_output_tokens": self.max_output_tokens,
        }
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

    def _request(self, payload: dict[str, object]) -> dict[str, object]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai provider")

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60, context=openai_ssl_context()) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:800]
            raise ProviderRequestError(
                f"OpenAI API request failed with HTTP {exc.code}: {body}",
                retryable=is_retryable_http_error(exc.code, body),
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderRequestError(
                f"OpenAI API request failed: {exc.reason}", retryable=True,
            ) from exc
        except (TimeoutError, ConnectionError, http.client.HTTPException) as exc:
            raise ProviderRequestError(
                f"OpenAI API request failed: {type(exc).__name__}: {exc}", retryable=True,
            ) from exc


def is_retryable_http_error(status: int, body: str) -> bool:
    if status == 429 and any(
        marker in body.lower() for marker in ("insufficient_quota", "credit_balance")
    ):
        return False
    return status in {408, 409, 429, 500, 502, 503, 504}


def openai_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def provider_system_prompt(
    profile: PromptProfile = "conservative",
    *,
    task_planning: bool = False,
) -> str:
    base = (
        "You are TermAgent, a terminal coding agent. Choose exactly one tool call. "
        "Start by gathering evidence with the configured verifier command, code_map, "
        "find_references, search, or read_file. "
        "Prefer code_map for Python, JavaScript, and TypeScript symbol discovery and find_references before broad edits. "
        "Do not use run_shell for file discovery; use search, code_map, find_references, or read_file instead. "
        "When running tests, call run_shell with exactly the configured verifier command. "
        "After a verifier failure, do not call run_shell again until after a write_file or write_patch_set succeeds. "
        "run_shell accepts one argv-style command only: no &&, ||, semicolons, pipes, command substitution, "
        "backticks, subshells, redirection, or chained inspection commands. "
        "Prefer minimal edits. "
        "Before writing a file, call plan_patch with the exact path and content you intend to write. "
        "If the task explicitly requires creating a missing file, an empty code map is sufficient "
        "evidence to plan that new file; use a repository-relative path. A configured verifier may "
        "be only a syntax or smoke check and may pass before the requested work is complete. "
        "For coordinated multi-file edits, call plan_patch_set with all files in the group. Only call "
        "write_file or write_patch_set after reviewing the matching plan diff. After writing files, "
        "rerun the configured tests. Use git_diff only when the work is done or you are blocked. "
        "Return only the structured tool call."
    )
    profiles = {
        "conservative": (
            " Avoid broad rewrites, avoid network commands unless explicitly configured, and recover from "
            "tool validation errors by choosing a safer evidence-gathering step."
        ),
        "benchmark": (
            " Optimize for reproducible benchmark success: run the verifier early, keep edits minimal, "
            "and finish only after a clean verifier result or a clear blocker."
        ),
        "fast": " Prefer the shortest safe path to a verified diff.",
    }
    planning = ""
    if task_planning:
        planning = (
            " After initial inspection and before any plan_patch call, use set_task_plan once. "
            "State the concrete deliverables, repository-relative output paths when known, and "
            "acceptance checks. Treat an empty repository or a passing smoke check as environment "
            "evidence, not proof that requested deliverables exist. Do not repeat identical discovery "
            "calls; move from discovery to a plan and then to implementation."
        )
    return base + planning + profiles[profile]


def tool_call_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "termagent_tool_call",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "arguments"],
            "properties": {
                "name": {
                    "type": "string",
                    "enum": [
                        "set_task_plan",
                        "search",
                        "read_file",
                        "code_map",
                        "find_references",
                        "plan_patch",
                        "plan_patch_set",
                        "write_file",
                        "write_patch_set",
                        "run_shell",
                        "git_diff",
                    ],
                },
                "arguments": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "summary",
                        "expected_paths",
                        "acceptance_checks",
                        "query",
                        "glob",
                        "path",
                        "start",
                        "limit",
                        "content",
                        "files",
                        "symbol",
                        "command",
                        "timeout",
                    ],
                    "properties": {
                        "summary": {"type": ["string", "null"]},
                        "expected_paths": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                        },
                        "acceptance_checks": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                        },
                        "query": {"type": ["string", "null"]},
                        "glob": {"type": ["string", "null"]},
                        "path": {"type": ["string", "null"]},
                        "start": {"type": ["integer", "null"]},
                        "limit": {"type": ["integer", "null"]},
                        "content": {"type": ["string", "null"]},
                        "files": {
                            "type": ["array", "null"],
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["path", "content"],
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                            },
                        },
                        "symbol": {"type": ["string", "null"]},
                        "command": {"type": ["string", "null"]},
                        "timeout": {"type": ["integer", "null"]},
                    },
                },
            },
        },
    }


def openai_tool_definitions() -> list[dict[str, object]]:
    return [
        openai_tool(
            "set_task_plan",
            "Register the task goal, expected output files, and acceptance checks before patch planning.",
            {
                "summary": {"type": "string"},
                "expected_paths": {"type": "array", "items": {"type": "string"}},
                "acceptance_checks": {"type": "array", "items": {"type": "string"}},
            },
        ),
        openai_tool(
            "search",
            "Search repository text with ripgrep when available.",
            {
                "query": {"type": "string"},
                "glob": {"type": ["string", "null"]},
            },
        ),
        openai_tool(
            "read_file",
            "Read a UTF-8 text file inside the repository.",
            {
                "path": {"type": "string"},
                "start": {"type": ["integer", "null"]},
                "limit": {"type": ["integer", "null"]},
            },
        ),
        openai_tool(
            "code_map",
            "Build a Python, JavaScript, and TypeScript code map with symbols and imports.",
            {
                "query": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"]},
            },
        ),
        openai_tool(
            "find_references",
            "Find Python, JavaScript, and TypeScript name references for a symbol.",
            {
                "symbol": {"type": "string"},
                "limit": {"type": ["integer", "null"]},
            },
        ),
        openai_tool(
            "plan_patch",
            "Preview a UTF-8 file write and return a unified diff without modifying the file.",
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        ),
        openai_tool(
            "plan_patch_set",
            "Preview multiple UTF-8 file writes as one grouped diff without modifying files.",
            {"files": patch_files_schema()},
        ),
        openai_tool(
            "write_file",
            "Write a UTF-8 text file inside the repository after a matching patch plan.",
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        ),
        openai_tool(
            "write_patch_set",
            "Write multiple UTF-8 files after a matching grouped patch plan.",
            {"files": patch_files_schema()},
        ),
        openai_tool(
            "run_shell",
            "Run a shell command under the configured safety policy.",
            {
                "command": {"type": "string"},
                "timeout": {"type": ["integer", "null"]},
            },
        ),
        openai_tool("git_diff", "Return the current git diff.", {}),
    ]


def openai_tool(name: str, description: str, properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        },
        "strict": True,
    }


def patch_files_schema() -> dict[str, object]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
    }


def extract_openai_tool_call(data: dict[str, object]) -> ToolCall:
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            name = item.get("name")
            arguments = item.get("arguments")
            if not isinstance(name, str):
                raise TypeError("function call name must be a string")
            if not isinstance(arguments, str):
                raise TypeError("function call arguments must be a JSON string")
            parsed = json.loads(arguments)
            if not isinstance(parsed, dict):
                raise TypeError("function call arguments must decode to an object")
            return ToolCall(name=name, arguments=parsed)

    text = extract_output_text(data)
    if text:
        return parse_tool_call(text)
    raise ValueError("response did not contain a function call")


def extract_output_text(data: dict[str, object]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(str(block["text"]))

    return "\n".join(parts).strip()


def parse_tool_call(text: str) -> ToolCall:
    if not text:
        raise ValueError("empty response")

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("response is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise TypeError("tool call must be a JSON object")
    if not isinstance(raw.get("name"), str):
        raise TypeError("tool call name must be a string")
    if not isinstance(raw.get("arguments"), dict):
        raise TypeError("tool call arguments must be an object")

    return ToolCall(name=str(raw["name"]), arguments=dict(raw["arguments"]))


def usage_from_response(data: dict[str, object]) -> TokenUsage:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return TokenUsage()

    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
    return TokenUsage(input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0))


def add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
    )


def compact_observations(observations: list[str], limit: int, max_chars: int) -> str:
    selected = observations[-limit:]
    text = "\n\n".join(selected)
    if len(text) <= max_chars:
        return text
    marker = "[older observation content truncated]\n"
    tail_size = max(0, max_chars - len(marker))
    return marker + text[-tail_size:]


def first_search_path(output: str) -> str | None:
    for line in output.splitlines():
        if ":" not in line:
            continue
        path = line.split(":", 1)[0].strip()
        if path.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
            return path
    return None


def first_code_map_symbol_path(output: str) -> str | None:
    match = re.search(r"-\s+[\w-]+\s+\w+\s+\w+\s+at\s+([^:\n]+\.(?:py|js|jsx|ts|tsx)):\d+", output)
    return match.group(1) if match else None


def symbol_from_task(task: str) -> str | None:
    match = re.search(r"\bfix\s+([A-Za-z_$][\w$]*)", task, flags=re.IGNORECASE)
    return match.group(1) if match else None


def strip_numbered_lines(output: str) -> str:
    lines: list[str] = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        _, content = line.split("|", 1)
        lines.append(content.removeprefix(" "))
    return "\n".join(lines) + "\n"


def patch_from_read_output(task: str, output: str) -> dict[str, str] | None:
    content = strip_numbered_lines(output)
    lowered_task = task.lower()
    path = read_path_from_observation(output)
    if not path:
        return None

    if "add" in lowered_task and "return a - b" in content:
        return {"path": path, "content": content.replace("return a - b", "return a + b")}

    if "subtract" in lowered_task and "return a + b" in content:
        return {"path": path, "content": content.replace("return a + b", "return a - b")}

    if "multiply" in lowered_task and "return a + b" in content:
        return {"path": path, "content": content.replace("return a + b", "return a * b")}

    if "divide" in lowered_task and "return a * b" in content:
        return {"path": path, "content": content.replace("return a * b", "return a / b")}

    if "clamp" in lowered_task and "return score" in content:
        return {"path": path, "content": content.replace("return score", "return min(max(score, 0), 100)")}

    if "slug" in lowered_task and "return text.lower()" in content:
        return {
            "path": path,
            "content": content.replace(
                "return text.lower()",
                'return "-".join(text.strip().lower().split())',
            ),
        }

    if "email" in lowered_task and "return email.strip()" in content:
        return {"path": path, "content": content.replace("return email.strip()", "return email.strip().lower()")}

    if "word" in lowered_task and "return len(text)" in content:
        return {"path": path, "content": content.replace("return len(text)", "return len(text.split())")}

    if "tax" in lowered_task and "return subtotal * (1 - taxRate);" in content:
        return {"path": path, "content": content.replace("return subtotal * (1 - taxRate);", "return subtotal * (1 + taxRate);")}

    return None


def patch_set_from_task(task: str) -> list[dict[str, str]] | None:
    lowered_task = task.lower()
    if "checkout" not in lowered_task or "discount" not in lowered_task or "tax" not in lowered_task:
        return None

    return [
        {
            "path": "pricing.py",
            "content": "def apply_discount(total, rate):\n    return total * (1 - rate)\n",
        },
        {
            "path": "tax.py",
            "content": "def add_tax(total, rate):\n    return total * (1 + rate)\n",
        },
    ]


def symbol_imported_by_test(output: str) -> str | None:
    path = read_path_from_observation(output)
    if not path or not path.rsplit("/", maxsplit=1)[-1].startswith("test_"):
        return None

    content = strip_numbered_lines(output)
    match = re.search(r"^from\s+\w+\s+import\s+([A-Za-z_]\w*)", content, flags=re.MULTILINE)
    return match.group(1) if match else None


def read_path_from_observation(output: str) -> str | None:
    match = re.search(r'"path":\s*"([^"]+)"', output)
    return match.group(1) if match else None


def build_provider(
    name: str,
    model: str | None = None,
    test_command: str | None = None,
    max_retries: int = 2,
    prompt_profile: PromptProfile = "conservative",
    observation_limit: int = 6,
    max_observation_chars: int = 8_000,
    max_output_tokens: int = 4_096,
    reasoning_effort: ReasoningEffort | None = None,
    task_planning: bool = False,
) -> Provider:
    if name == "mock":
        return MockProvider(RepairProvider(task_planning=task_planning))
    if name == "repair":
        return RepairProvider(
            test_command or f"{sys.executable} -m pytest -q",
            task_planning=task_planning,
        )
    if name == "openai":
        return OpenAICompatibleProvider(
            model or os.environ.get("TERMAGENT_MODEL", "gpt-5.6-luna"),
            test_command=test_command,
            max_retries=max_retries,
            prompt_profile=prompt_profile,
            observation_limit=observation_limit,
            max_observation_chars=max_observation_chars,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            task_planning=task_planning,
        )
    raise ValueError(f"unknown provider: {name}")
