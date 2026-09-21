"""Import the Harbor runtime directly from its wheel bundle without installation."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from termagent.harbor_runtime import (
    PythonRuntime,
    load_runtime_bundle,
    runtime_environment,
    runtime_metadata,
    runtime_validation_command,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel-dir", type=Path, default=Path(".termagent/release-wheels"))
    args = parser.parse_args()

    bundle = load_runtime_bundle(args.wheel_dir)
    runtime = PythonRuntime(
        executable=sys.executable,
        version=(sys.version_info.major, sys.version_info.minor, sys.version_info.micro),
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    }
    environment.update(runtime_environment(bundle))

    with tempfile.TemporaryDirectory(prefix="termagent-harbor-runtime-") as temp:
        result = subprocess.run(
            shlex.split(runtime_validation_command(runtime)),
            cwd=temp,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)

    print(json.dumps(runtime_metadata(bundle, runtime), indent=2, sort_keys=True))
    print("Portable Harbor wheel runtime passed without pip or venv.")


if __name__ == "__main__":
    main()
