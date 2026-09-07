"""Container-side entry point; Harbor imports remain outside the agent runtime."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .agent import TerminalAgent
from .models import AgentConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    settings["repo"] = Path(settings["repo"])
    settings["log_dir"] = Path(settings["log_dir"])
    state = TerminalAgent(AgentConfig(**settings)).run()
    destination = settings["log_dir"].parent / "summary.json"
    destination.write_text(json.dumps(asdict(state), indent=2) + "\n")
    print(state.final_answer)
    return 0 if state.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
