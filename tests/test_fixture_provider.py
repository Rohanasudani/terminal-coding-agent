from termagent.fixture_provider import FixtureProvider, symbol_imported_by_test
from termagent.models import ToolCall
from termagent.provider import build_provider


def test_fixture_provider_registers_plan_when_enabled():
    provider = FixtureProvider(test_command="pytest -q", task_planning=True)

    first = provider.next_action("Fix the bug", []).tool_call

    assert first == ToolCall("run_shell", {"command": "pytest -q", "timeout": 60})


def test_fixture_provider_plans_known_patch_before_preview():
    provider = FixtureProvider(test_command="pytest -q", task_planning=True)
    observation = (
        'read_file: ok\nmetadata: {"path": "calculator.py"}\n'
        "   1 | def add(a, b):\n   2 |     return a - b"
    )

    plan = provider.next_action("Fix the add bug", [observation]).tool_call
    preview = provider.next_action(
        "Fix the add bug",
        [observation, "set_task_plan: ok\nmetadata: {}\nGoal: Fix the add bug"],
    ).tool_call

    assert plan.name == "set_task_plan"
    assert plan.arguments["expected_paths"] == ["calculator.py"]
    assert preview.name == "plan_patch"


def test_symbol_imported_by_test_extracts_imported_function():
    observation = """
read_file: ok
metadata: {"path": "/tmp/repo/test_users.py"}
   1 | from users import normalize_email
   2 |
   3 | def test_lowercases_email():
   4 |     assert normalize_email("MAYA@EXAMPLE.COM") == "maya@example.com"
"""

    assert symbol_imported_by_test(observation) == "normalize_email"


def test_legacy_repair_name_resolves_to_fixture_provider():
    provider = build_provider("repair", test_command="pytest -q")

    assert isinstance(provider, FixtureProvider)
