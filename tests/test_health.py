from pathlib import Path

from termagent.health import (
    HealthCheck,
    format_health_checks,
    health_checks_as_dicts,
    health_checks_passed,
    run_health_checks,
)


def test_health_checks_report_repository_status(tmp_path: Path):
    checks = run_health_checks(tmp_path)

    assert any(check.name == "repo" and check.status == "warn" for check in checks)


def test_health_format_and_status_helpers():
    checks = [
        HealthCheck("python", "pass", "3.13"),
        HealthCheck("openai", "warn", "missing key"),
    ]

    assert health_checks_passed(checks)
    assert health_checks_as_dicts(checks)[0]["name"] == "python"
    assert "PASS" in format_health_checks(checks)
