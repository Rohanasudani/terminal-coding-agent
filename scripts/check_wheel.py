"""Install a built wheel offline and repair a fixture outside the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel-dir", type=Path, default=Path(".termagent/release-wheels"))
    parser.add_argument("--record", type=Path, help="Optional asciicast v2 terminal recording")
    args = parser.parse_args()
    wheel_dir = args.wheel_dir.resolve()
    root = Path(__file__).resolve().parents[1]
    task = root / "bench" / "tasks" / "bugfix_javascript_total"
    spec = json.loads((task / "task.json").read_text())
    environment = {key: value for key, value in os.environ.items() if key in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
    }}

    with tempfile.TemporaryDirectory(prefix="termagent-wheel-") as temp:
        directory = Path(temp)
        install = directory / "venv"
        venv.EnvBuilder(with_pip=True).create(install)
        binaries = install / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")
        termagent = binaries / ("termagent.exe" if os.name == "nt" else "termagent")
        subprocess.run([
            str(python), "-m", "pip", "install", "--no-index", "--find-links",
            str(wheel_dir), "terminal-coding-agent",
        ], cwd=directory, env=environment, check=True, timeout=90)
        repo = directory / "repo"
        shutil.copytree(task / "repo", repo)
        started = time.monotonic()
        result = subprocess.run([
            str(termagent), "run", "--repo", str(repo),
            "--provider", "repair", "--task", spec["instruction"],
            "--test-command", spec["verify"], "--approval-mode", "auto",
            "--log-dir", str(directory / "traces"),
        ], cwd=directory, env=environment, capture_output=True, text=True, timeout=90, check=False)
        elapsed = time.monotonic() - started
        output = result.stdout + result.stderr
        print(output)
        result.check_returncode()
        subprocess.run(["node", "test_cart.js"], cwd=repo, env=environment, check=True, timeout=30)

        if args.record:
            prompt = (
                "Deterministic repair provider; clean wheel install; no API calls.\r\n"
                '$ termagent run --repo /tmp/demo-repo --provider repair '
                '--task "Fix totalWithTax and run tests" '
                '--test-command "node test_cart.js" --approval-mode auto\r\n'
            )
            events = [
                {"version": 2, "width": 110, "height": 32, "title": "TermAgent installed-wheel demo (deterministic)"},
                [0.0, "o", prompt],
                [round(elapsed, 3), "o", output.replace(str(directory), "/tmp/demo").replace("\n", "\r\n")],
            ]
            args.record.parent.mkdir(parents=True, exist_ok=True)
            args.record.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    print("Clean wheel installation and independent JavaScript verifier passed.")


if __name__ == "__main__":
    main()
