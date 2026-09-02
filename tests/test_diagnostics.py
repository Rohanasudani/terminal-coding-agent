from termagent.diagnostics import parse_pytest_failure
from termagent.diagnostics import tests_passed as did_tests_pass


def test_parse_pytest_failure_extracts_file_symbol_and_assertion():
    output = """
    tests/test_calculator.py:5: AssertionError
    E       assert -1 == 5
    E        +  where -1 = add(2, 3)
    """

    failure = parse_pytest_failure(output)

    assert failure.file_path == "tests/test_calculator.py"
    assert failure.symbol == "add"
    assert failure.assertion == "-1 == 5"


def test_tests_passed_detects_clean_pytest_output():
    assert did_tests_pass(".. [100%]\n2 passed in 0.01s") is True
    assert did_tests_pass("1 failed, 1 passed") is False
