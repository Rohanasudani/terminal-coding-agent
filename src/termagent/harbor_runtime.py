from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MIN_RUNTIME_PYTHON = (3, 11)
CONTAINER_WHEEL_DIR = PurePosixPath("/opt/termagent-wheels")
PYTHON_CANDIDATES = (
    "python3.13",
    "python3.12",
    "python3.11",
    "python3",
)
PURE_WHEEL_PATTERN = re.compile(r"^[A-Za-z0-9_.+-]+-py3-none-any\.whl$")


@dataclass(frozen=True)
class WheelArtifact:
    path: Path
    sha256: str

    @property
    def container_path(self) -> PurePosixPath:
        return CONTAINER_WHEEL_DIR / self.path.name


@dataclass(frozen=True)
class RuntimeBundle:
    artifacts: tuple[WheelArtifact, ...]
    termagent_sha256: str
    bundle_sha256: str

    @property
    def pythonpath(self) -> str:
        return ":".join(str(artifact.container_path) for artifact in self.artifacts)


@dataclass(frozen=True)
class PythonRuntime:
    executable: str
    version: tuple[int, int, int]


def load_runtime_bundle(wheel_dir: Path) -> RuntimeBundle:
    directory = wheel_dir.resolve()
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("wheel_dir must be a real directory")

    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        raise ValueError("wheel_dir must contain the TermAgent wheel and its dependencies")
    if any(path.is_symlink() or not path.is_file() for path in wheels):
        raise ValueError("runtime wheel artifacts must be regular files")
    if any(not PURE_WHEEL_PATTERN.fullmatch(path.name) for path in wheels):
        raise ValueError("Harbor runtime wheels must use the pure-Python py3-none-any tag")

    termagent = [path for path in wheels if path.name.startswith("terminal_coding_agent-")]
    if len(termagent) != 1:
        raise ValueError("wheel_dir must contain exactly one TermAgent wheel")
    certifi = [path for path in wheels if path.name.startswith("certifi-")]
    if len(certifi) != 1:
        raise ValueError("wheel_dir must contain exactly one certifi runtime dependency")

    artifacts = tuple(
        WheelArtifact(path=path, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in wheels
    )
    digest = hashlib.sha256()
    for artifact in artifacts:
        digest.update(artifact.path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(artifact.sha256.encode("ascii"))
        digest.update(b"\n")
    termagent_hash = next(
        artifact.sha256
        for artifact in artifacts
        if artifact.path.name.startswith("terminal_coding_agent-")
    )
    return RuntimeBundle(
        artifacts=artifacts,
        termagent_sha256=termagent_hash,
        bundle_sha256=digest.hexdigest(),
    )


def python_probe_command(candidate: str) -> str:
    script = (
        "import json,sys; "
        "print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:3])})); "
        f"raise SystemExit(0 if sys.version_info >= {MIN_RUNTIME_PYTHON!r} else 3)"
    )
    return shlex.join([candidate, "-c", script])


def python_bootstrap_command() -> str:
    return (
        "set -eu; "
        "if command -v apt-get >/dev/null 2>&1; then "
        "export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; "
        "apt-get install -y -qq python3; "
        "elif command -v apk >/dev/null 2>&1; then apk add --no-cache python3; "
        "elif command -v dnf >/dev/null 2>&1; then dnf install -y python3; "
        "else echo 'no supported package manager for Python bootstrap' >&2; exit 127; fi"
    )


def parse_python_probe(output: str) -> PythonRuntime:
    for line in reversed(output.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        executable = payload.get("executable") if isinstance(payload, dict) else None
        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(executable, str) or not PurePosixPath(executable).is_absolute():
            continue
        if not isinstance(version, list) or len(version) != 3 or not all(
            isinstance(item, int) for item in version
        ):
            continue
        parsed = tuple(version)
        if parsed < (*MIN_RUNTIME_PYTHON, 0):
            raise ValueError("container Python is older than 3.11")
        return PythonRuntime(executable=executable, version=parsed)
    raise ValueError("Python probe did not return valid runtime metadata")


def runtime_validation_command(runtime: PythonRuntime) -> str:
    script = (
        "import termagent; "
        "from termagent.provider import openai_ssl_context; "
        "openai_ssl_context(); "
        "print('termagent-runtime-ok')"
    )
    return shlex.join([runtime.executable, "-c", script])


def runtime_environment(bundle: RuntimeBundle, extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(extra or {})
    environment["PYTHONPATH"] = bundle.pythonpath
    return environment


def format_probe_failure(candidate: str, return_code: int, output: str) -> str:
    detail = " ".join(output.strip().split())[:160] or "no output"
    return f"{candidate} (exit {return_code}: {detail})"


def runtime_metadata(bundle: RuntimeBundle, runtime: PythonRuntime) -> dict[str, object]:
    return {
        "runtime_bundle_sha256": bundle.bundle_sha256,
        "runtime_wheels": [artifact.path.name for artifact in bundle.artifacts],
        "runtime_python": ".".join(str(part) for part in runtime.version),
        "runtime_python_executable": runtime.executable,
        "runtime_install_mode": "wheel-pythonpath",
    }
