"""Discovery and execution of YubaLANG output-based tests."""

import subprocess
import sys
from pathlib import Path


TEST_TIMEOUT_SECONDS = 10


def _interpreter_command(program: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, str(program)]
    entry_point = Path(__file__).resolve().parent.parent / "YubaLANG.py"
    return [sys.executable, str(entry_point), str(program)]


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _first_difference(expected: str, actual: str) -> str:
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    for index, (expected_line, actual_line) in enumerate(
        zip(expected_lines, actual_lines), start=1
    ):
        if expected_line != actual_line:
            return f"line {index}: expected {expected_line!r}, got {actual_line!r}"
    if len(expected_lines) != len(actual_lines):
        index = min(len(expected_lines), len(actual_lines)) + 1
        expected_line = expected_lines[index - 1] if index <= len(expected_lines) else "<end of output>"
        actual_line = actual_lines[index - 1] if index <= len(actual_lines) else "<end of output>"
        return f"line {index}: expected {expected_line!r}, got {actual_line!r}"
    return f"line {max(1, len(expected_lines))}: trailing newline differs"


def _run_case(program: Path) -> tuple[str, str]:
    expected_file = program.with_suffix(".expected.txt")
    if not expected_file.is_file():
        return "ERROR", f"missing expected-output file: {expected_file}"

    try:
        with expected_file.open("r", encoding="utf-8", newline="") as source:
            expected = _normalize_newlines(source.read())
        result = subprocess.run(
            _interpreter_command(program),
            cwd=program.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, UnicodeError) as error:
        return "ERROR", str(error)
    except subprocess.TimeoutExpired:
        return "ERROR", f"timed out after {TEST_TIMEOUT_SECONDS} seconds"

    if result.returncode != 0:
        detail = _normalize_newlines(result.stdout + result.stderr).strip()
        if not detail:
            detail = f"interpreter exited with status {result.returncode}"
        return "ERROR", detail

    actual = _normalize_newlines(result.stdout)
    if actual != expected:
        return "FAIL", _first_difference(expected, actual)
    return "PASS", ""


def run_tests(path: Path) -> int:
    """Run all .yl tests under a directory, or one .yl test file."""
    path = path.resolve()

    if path.is_file() and path.suffix == ".yl":
        programs = [path]
    elif path.is_dir():
        programs = sorted(path.rglob("*.yl"))
    else:
        print(f"test: not a .yl file or directory: {path}", file=sys.stderr)
        return 2

    if not programs:
        print(f"test: no .yl tests found in {path}", file=sys.stderr)
        return 1

    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    for program in programs:
        status, detail = _run_case(program)
        counts[status] += 1
        print(f"{status}: {program}")
        if detail:
            print(f"  {detail}")

    print(
        f"Results: {counts['PASS']} passed, {counts['FAIL']} failed, "
        f"{counts['ERROR']} errored"
    )
    return 1 if counts["FAIL"] or counts["ERROR"] else 0
