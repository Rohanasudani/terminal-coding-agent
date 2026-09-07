import json
import shutil
import sys
from pathlib import Path
from shlex import quote

import pytest

from termagent.grading import grade_workspace


def test_grader_uses_original_tests_and_only_solution_files(tmp_path):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    candidate = tmp_path / "candidate"
    shutil.copytree(source, candidate)
    (candidate / "test_calculator.py").write_text("def test_fake():\n    pass\n")
    command = f"{quote(sys.executable)} -m pytest -q"

    assert not grade_workspace(source, candidate, ["calculator.py"], command).passed
    (candidate / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    assert grade_workspace(source, candidate, ["calculator.py"], command).passed


def test_grader_rejects_escaping_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("value = 0\n")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("value = 1\n")
    (candidate / "module.py").symlink_to(outside)

    result = grade_workspace(source, candidate, ["module.py"], "does-not-exist")
    assert not result.passed
    assert "escapes repository root" in result.output


def test_grader_timeout_is_a_failed_result(tmp_path):
    (tmp_path / "wait.py").write_text("import time\ntime.sleep(10)\n")
    result = grade_workspace(tmp_path, tmp_path, ["wait.py"], f"{quote(sys.executable)} wait.py", timeout=0.05)
    assert not result.passed
    assert result.returncode is None
    assert "timed out" in result.output


def test_grader_does_not_inherit_provider_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--invalid-option")
    (tmp_path / "verify.py").write_text(
        "import os\nassert 'OPENAI_API_KEY' not in os.environ\n"
        "assert 'PYTEST_ADDOPTS' not in os.environ\n"
    )
    assert grade_workspace(tmp_path, tmp_path, ["verify.py"], f"{quote(sys.executable)} verify.py").passed


REFERENCE_SOLUTIONS = {
    "pagination": {
        "pagination.py": (
            "def collect_records(fetch_page):\n"
            "    records, seen, cursor = [], set(), None\n"
            "    while True:\n"
            "        if cursor in seen:\n"
            "            raise ValueError('repeated cursor')\n"
            "        seen.add(cursor)\n"
            "        page = fetch_page(cursor)\n"
            "        records.extend(page['items'])\n"
            "        cursor = page['next_cursor']\n"
            "        if cursor is None:\n"
            "            return records\n"
        ),
    },
    "config_precedence": {
        "settings.py": "def resolve_settings(defaults, environment, overrides):\n    return {**defaults, **environment, **overrides}\n",
        "service.py": "from settings import resolve_settings\ndef create_service(defaults, environment, overrides):\n    return {'settings': resolve_settings(defaults, environment, overrides)}\n",
    },
    "cache_expiry": {
        "cache.js": (
            "class ExpiringCache {\n"
            "  constructor(now) { this.now = now; this.entries = new Map(); }\n"
            "  set(key, value, ttl) { this.entries.set(key, {value, expiresAt: this.now() + ttl}); }\n"
            "  has(key) {\n"
            "    const entry = this.entries.get(key);\n"
            "    if (!entry) return false;\n"
            "    if (this.now() >= entry.expiresAt) { this.entries.delete(key); return false; }\n"
            "    return true;\n"
            "  }\n"
            "  get(key) { return this.has(key) ? this.entries.get(key).value : undefined; }\n"
            "}\nmodule.exports = { ExpiringCache };\n"
        ),
    },
}


@pytest.mark.parametrize("task_name", REFERENCE_SOLUTIONS)
def test_evaluation_fixture_fails_before_and_passes_with_reference_fix(tmp_path, task_name):
    task = Path(__file__).parents[1] / "bench" / "evaluation" / task_name
    spec = json.loads((task / "task.json").read_text())
    source = task / "repo"
    candidate = tmp_path / "candidate"
    shutil.copytree(source, candidate)
    command = spec["verify"].format(python=quote(sys.executable))
    baseline = grade_workspace(source, candidate, spec["solution_files"], command)
    assert not baseline.passed
    assert baseline.returncode == 1, baseline.output
    for name, content in REFERENCE_SOLUTIONS[task_name].items():
        (candidate / name).write_text(content)
    fixed = grade_workspace(source, candidate, spec["solution_files"], command)
    assert fixed.passed, fixed.output
