from termagent.completion import (
    assess_completion,
    classify_verifier,
    extract_changed_paths,
    is_targeted_check,
    validate_completion_review,
)


def test_verifier_strength_distinguishes_tests_from_smoke_checks():
    assert classify_verifier("python -m pytest -q") == "behavioral"
    assert classify_verifier("node --test") == "behavioral"
    assert classify_verifier("uv run pytest -q") == "behavioral"
    assert classify_verifier("python -m compileall -q /app") == "smoke"
    assert classify_verifier("python app.py --check") == "custom"
    assert classify_verifier("echo pytest") == "custom"


def test_targeted_check_accepts_test_runner_or_declared_output():
    expected = ("src/report.py",)

    assert is_targeted_check("pytest -q", expected)
    assert is_targeted_check("python src/report.py --sample", expected)
    assert is_targeted_check("./src/report.py --sample", expected)
    assert not is_targeted_check("python -m compileall -q src", expected)
    assert not is_targeted_check("echo src/report.py", expected)


def test_extract_changed_paths_includes_created_modified_and_deleted_files():
    diff = """--- a/old.py
+++ b/old.py
@@ -1 +1 @@
-old
+new
--- a/deleted.py
+++ /dev/null
--- /dev/null
+++ b/created.py
"""

    assert extract_changed_paths(diff) == ("created.py", "deleted.py", "old.py")


def test_strict_completion_requires_changed_outputs_review_and_behavioral_evidence():
    review = validate_completion_review(
        [{"criterion": "report is generated", "evidence": "pytest covered report output"}],
        ["only the configured cases were exercised"],
        True,
    )

    assessment = assess_completion(
        diff="--- a/src/report.py\n+++ b/src/report.py\n",
        verifier_passed=True,
        verifier_command="python -m pytest -q",
        require_changes=True,
        expected_paths=("src/report.py",),
        acceptance_checks=("report is generated",),
        strict=True,
        review=review,
    )

    assert assessment.passed
    assert assessment.blockers == ()
    assert assessment.changed_paths == ("src/report.py",)


def test_strict_completion_rejects_smoke_only_evidence_and_missing_output():
    review = validate_completion_review(
        [{"criterion": "service works", "evidence": "source compiles"}],
        [],
        True,
    )

    assessment = assess_completion(
        diff="--- a/README.md\n+++ b/README.md\n",
        verifier_passed=True,
        verifier_command="python -m compileall -q /app",
        require_changes=True,
        expected_paths=("service.py",),
        acceptance_checks=("service works",),
        strict=True,
        review=review,
    )

    assert not assessment.passed
    assert any("absent from the final diff" in blocker for blocker in assessment.blockers)
    assert any("only a smoke check" in blocker for blocker in assessment.blockers)


def test_targeted_execution_can_strengthen_a_smoke_verifier():
    review = validate_completion_review(
        [{"criterion": "program handles sample", "evidence": "sample command exited zero"}],
        [],
        True,
    )

    assessment = assess_completion(
        diff="--- a/main.py\n+++ b/main.py\n",
        verifier_passed=True,
        verifier_command="python -m compileall -q main.py",
        require_changes=True,
        expected_paths=("main.py",),
        acceptance_checks=("program handles sample",),
        strict=True,
        review=review,
        completion_checks=("python main.py --sample",),
    )

    assert assessment.passed
