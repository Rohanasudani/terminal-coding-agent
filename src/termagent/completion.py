from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

VerifierStrength = Literal["behavioral", "smoke", "custom"]


@dataclass(frozen=True)
class AcceptanceEvidence:
    criterion: str
    evidence: str


@dataclass(frozen=True)
class CompletionReview:
    acceptance_evidence: tuple[AcceptanceEvidence, ...]
    residual_risks: tuple[str, ...]
    ready: bool


@dataclass(frozen=True)
class CompletionAssessment:
    passed: bool
    blockers: tuple[str, ...]
    changed_paths: tuple[str, ...]
    verifier_strength: VerifierStrength


def classify_verifier(command: str) -> VerifierStrength:
    try:
        parts = shlex.split(command)
    except ValueError:
        return "custom"
    executable = Path(parts[0]).name.lower()
    arguments = [part.lower() for part in parts[1:]]

    if executable == "uv" and len(arguments) >= 2 and arguments[0] == "run":
        return classify_verifier(shlex.join(parts[2:]))
    if executable.startswith("python"):
        if len(arguments) >= 2 and arguments[0] == "-m":
            if arguments[1] in {"pytest", "unittest"}:
                return "behavioral"
            if arguments[1] in {"compileall", "py_compile", "mypy", "ruff"}:
                return "smoke"
        return "custom"
    if executable in {"pytest", "py.test", "unittest", "ctest"}:
        return "behavioral"
    if executable == "node" and "--test" in arguments:
        return "behavioral"
    if executable in {"npm", "pnpm", "yarn"} and (
        arguments[:1] == ["test"] or arguments[:2] == ["run", "test"]
    ):
        return "behavioral"
    if (
        executable in {"go", "cargo", "dotnet", "mvn", "gradle", "gradlew", "make"}
        and arguments[:1] == ["test"]
    ):
        return "behavioral"
    if executable in {"eslint", "mypy", "ruff", "tsc"}:
        return "smoke"
    return "custom"


def is_targeted_check(command: str, expected_paths: tuple[str, ...]) -> bool:
    strength = classify_verifier(command)
    if strength == "behavioral":
        return True
    if strength == "smoke":
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    executable = Path(parts[0]).name.lower()
    runners = {
        "bash", "bun", "deno", "dotnet", "java", "node", "perl", "php", "ruby", "sh", "zsh",
    }
    if not (executable.startswith("python") or executable in runners):
        return _matches_expected_path(parts[0], expected_paths)
    return any(_matches_expected_path(argument, expected_paths) for argument in parts[1:])


def _matches_expected_path(value: str, expected_paths: tuple[str, ...]) -> bool:
    normalized = value.removeprefix("./").lstrip("/")
    return any(normalized == path or normalized.endswith("/" + path) for path in expected_paths)


def extract_changed_paths(diff: str) -> tuple[str, ...]:
    paths: set[str] = set()
    for line in diff.splitlines():
        candidate: str | None = None
        if line.startswith(("+++ b/", "--- a/")):
            candidate = line[6:]
        if candidate and candidate != "/dev/null":
            paths.add(candidate)
    return tuple(sorted(paths))


def validate_completion_review(
    acceptance_evidence: object,
    residual_risks: object,
    ready: object,
) -> CompletionReview:
    if not isinstance(acceptance_evidence, list) or len(acceptance_evidence) > 20:
        raise TypeError("acceptance_evidence must be a list with at most 20 entries")
    evidence: list[AcceptanceEvidence] = []
    for item in acceptance_evidence:
        if not isinstance(item, dict):
            raise TypeError("acceptance evidence entries must be objects")
        criterion = item.get("criterion")
        detail = item.get("evidence")
        if not isinstance(criterion, str) or not criterion.strip():
            raise TypeError("acceptance evidence criterion must be a non-empty string")
        if not isinstance(detail, str) or not detail.strip():
            raise TypeError("acceptance evidence detail must be a non-empty string")
        if len(criterion) > 1_000 or len(detail) > 2_000:
            raise ValueError("acceptance evidence entry is too long")
        evidence.append(AcceptanceEvidence(criterion.strip(), detail.strip()))

    if not isinstance(residual_risks, list) or len(residual_risks) > 20 or not all(
        isinstance(risk, str) and risk.strip() and len(risk) <= 1_000
        for risk in residual_risks
    ):
        raise TypeError("residual_risks must be a list of non-empty bounded strings")
    if not isinstance(ready, bool):
        raise TypeError("ready must be a boolean")
    return CompletionReview(
        acceptance_evidence=tuple(evidence),
        residual_risks=tuple(risk.strip() for risk in residual_risks),
        ready=ready,
    )


def assess_completion(
    *,
    diff: str,
    verifier_passed: bool,
    verifier_command: str,
    require_changes: bool,
    expected_paths: tuple[str, ...],
    acceptance_checks: tuple[str, ...],
    strict: bool,
    review: CompletionReview | None,
    completion_checks: tuple[str, ...] = (),
) -> CompletionAssessment:
    changed_paths = extract_changed_paths(diff)
    strength = classify_verifier(verifier_command)
    blockers: list[str] = []
    has_diff = diff.strip() not in {"", "no diff"}

    if not verifier_passed:
        blockers.append("the configured verifier has not passed after the latest mutation")
    if require_changes and not has_diff:
        blockers.append("the final diff does not contain a repository change")

    missing_changes = sorted(set(expected_paths) - set(changed_paths))
    if strict and require_changes and not changed_paths:
        blockers.append("the final diff does not expose parseable changed paths")
    if strict and missing_changes:
        blockers.append("declared outputs are absent from the final diff: " + ", ".join(missing_changes))

    if strict:
        if review is None:
            blockers.append("a structured completion review is required")
        elif not review.ready:
            blockers.append("the completion review did not mark the task ready")
        else:
            reviewed = [item.criterion for item in review.acceptance_evidence]
            missing_evidence = [check for check in acceptance_checks if check not in reviewed]
            unexpected_evidence = [criterion for criterion in reviewed if criterion not in acceptance_checks]
            if missing_evidence:
                blockers.append(
                    "acceptance checks lack review evidence: " + ", ".join(missing_evidence)
                )
            if unexpected_evidence:
                blockers.append(
                    "completion review contains undeclared criteria: "
                    + ", ".join(unexpected_evidence)
                )
        if strength == "smoke" and not completion_checks:
            blockers.append(
                "the configured verifier is only a smoke check; run a behavioral test or execute "
                "a declared output before claiming completion"
            )

    return CompletionAssessment(
        passed=not blockers,
        blockers=tuple(blockers),
        changed_paths=changed_paths,
        verifier_strength=strength,
    )
