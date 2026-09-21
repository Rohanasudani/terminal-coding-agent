import hashlib
import json
from pathlib import Path

import pytest

from termagent.harbor_runtime import (
    PythonRuntime,
    format_probe_failure,
    load_runtime_bundle,
    parse_python_probe,
    python_probe_command,
    runtime_environment,
    runtime_metadata,
    runtime_validation_command,
)


def write_bundle(directory: Path) -> None:
    directory.mkdir()
    (directory / "terminal_coding_agent-0.1.0-py3-none-any.whl").write_bytes(b"agent")
    (directory / "certifi-2026.7.22-py3-none-any.whl").write_bytes(b"certifi")


def test_load_runtime_bundle_records_all_artifacts_and_hashes(tmp_path: Path):
    wheels = tmp_path / "wheels"
    write_bundle(wheels)

    bundle = load_runtime_bundle(wheels)

    assert [artifact.path.name for artifact in bundle.artifacts] == [
        "certifi-2026.7.22-py3-none-any.whl",
        "terminal_coding_agent-0.1.0-py3-none-any.whl",
    ]
    assert bundle.termagent_sha256 == hashlib.sha256(b"agent").hexdigest()
    assert len(bundle.bundle_sha256) == 64
    assert bundle.pythonpath == (
        "/opt/termagent-wheels/certifi-2026.7.22-py3-none-any.whl:"
        "/opt/termagent-wheels/terminal_coding_agent-0.1.0-py3-none-any.whl"
    )


@pytest.mark.parametrize(
    ("filename", "message"),
    [
        (None, "certifi"),
        ("native-1.0.0-cp313-cp313-manylinux.whl", "pure-Python"),
    ],
)
def test_runtime_bundle_rejects_incomplete_or_native_artifacts(
    tmp_path: Path, filename: str | None, message: str,
):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "terminal_coding_agent-0.1.0-py3-none-any.whl").write_bytes(b"agent")
    if filename:
        (wheels / "certifi-2026.7.22-py3-none-any.whl").write_bytes(b"certifi")
        (wheels / filename).write_bytes(b"native")

    with pytest.raises(ValueError, match=message):
        load_runtime_bundle(wheels)


def test_runtime_bundle_rejects_duplicate_certifi_wheels(tmp_path: Path):
    wheels = tmp_path / "wheels"
    write_bundle(wheels)
    (wheels / "certifi-2027.1.1-py3-none-any.whl").write_bytes(b"new certifi")

    with pytest.raises(ValueError, match="exactly one certifi"):
        load_runtime_bundle(wheels)


def test_parse_python_probe_uses_last_valid_json_line():
    output = "startup warning\n" + json.dumps({
        "executable": "/usr/local/bin/python3.12",
        "version": [3, 12, 4],
    })

    runtime = parse_python_probe(output)

    assert runtime == PythonRuntime("/usr/local/bin/python3.12", (3, 12, 4))


@pytest.mark.parametrize(
    "payload",
    [
        {"executable": "python3", "version": [3, 12, 0]},
        {"executable": "/usr/bin/python3", "version": [3, 10, 14]},
        {"executable": "/usr/bin/python3", "version": [3, "12", 0]},
    ],
)
def test_parse_python_probe_rejects_unsupported_metadata(payload: dict[str, object]):
    with pytest.raises(ValueError):
        parse_python_probe(json.dumps(payload))


def test_runtime_commands_do_not_require_pip_or_venv(tmp_path: Path):
    wheels = tmp_path / "wheels"
    write_bundle(wheels)
    bundle = load_runtime_bundle(wheels)
    runtime = PythonRuntime("/usr/local/bin/python3.11", (3, 11, 9))

    probe = python_probe_command("python3.11")
    validation = runtime_validation_command(runtime)
    environment = runtime_environment(bundle, {"OPENAI_API_KEY": "test-secret"})

    assert "pip" not in probe + validation
    assert "venv" not in probe + validation
    assert "openai_ssl_context" in validation
    assert environment["OPENAI_API_KEY"] == "test-secret"
    assert environment["PYTHONPATH"] == bundle.pythonpath
    assert "test-secret" not in validation


def test_runtime_environment_does_not_allow_pythonpath_override(tmp_path: Path):
    wheels = tmp_path / "wheels"
    write_bundle(wheels)
    bundle = load_runtime_bundle(wheels)

    environment = runtime_environment(bundle, {"PYTHONPATH": "/tmp/untrusted"})

    assert environment["PYTHONPATH"] == bundle.pythonpath


def test_runtime_metadata_is_reproducible(tmp_path: Path):
    wheels = tmp_path / "wheels"
    write_bundle(wheels)
    bundle = load_runtime_bundle(wheels)
    runtime = PythonRuntime("/usr/bin/python3", (3, 13, 7))

    metadata = runtime_metadata(bundle, runtime)

    assert metadata["runtime_bundle_sha256"] == bundle.bundle_sha256
    assert metadata["runtime_python"] == "3.13.7"
    assert metadata["runtime_install_mode"] == "wheel-pythonpath"


def test_probe_failure_is_bounded_and_single_line():
    detail = format_probe_failure("python3", 127, "not found\n" + "x" * 300)

    assert detail.startswith("python3 (exit 127: not found")
    assert "\n" not in detail
    assert len(detail) < 200
