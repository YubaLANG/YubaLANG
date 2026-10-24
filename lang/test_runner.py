"""Discovery and execution of YubaLANG output-based tests."""

import difflib
import json
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


def _run_case(program: Path) -> tuple[str, str, str, str]:
    expected_file = program.with_suffix(".expected.txt")
    if not expected_file.is_file():
        return "ERROR", f"missing expected-output file: {expected_file}", "", ""

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
        return "ERROR", str(error), "", ""
    except subprocess.TimeoutExpired:
        return "ERROR", f"timed out after {TEST_TIMEOUT_SECONDS} seconds", "", ""

    if result.returncode != 0:
        detail = _normalize_newlines(result.stdout + result.stderr).strip()
        if not detail:
            detail = f"interpreter exited with status {result.returncode}"
        return "ERROR", detail, expected, _normalize_newlines(result.stdout)

    actual = _normalize_newlines(result.stdout)
    if actual != expected:
        return "FAIL", _first_difference(expected, actual), expected, actual
    return "PASS", "", expected, actual


def run_tests(
    path: Path,
    filter_pattern: str | None = None,
    output_format: str = "text",
) -> int:
    """Run all .yl tests under a directory, or one .yl test file."""
    path = path.resolve()

    if path.is_file() and path.suffix == ".yl":
        programs = [path]
    elif path.is_dir():
        programs = sorted(path.rglob("*.yl"))
    else:
        print(f"test: not a .yl file or directory: {path}", file=sys.stderr)
        return 2

    if filter_pattern:
        pattern = filter_pattern.casefold()
        programs = [
            program for program in programs
            if pattern in program.stem.casefold()
            or pattern in str(program.relative_to(path if path.is_dir() else path.parent)).casefold()
        ]
    if not programs:
        if output_format == "json":
            print(json.dumps({
                "path": str(path), "filter": filter_pattern,
                "counts": {"PASS": 0, "FAIL": 0, "ERROR": 0}, "tests": [],
            }, indent=2))
        else:
            message = "no .yl tests matched" if filter_pattern else "no .yl tests found"
            print(f"test: {message} in {path}", file=sys.stderr)
        return 1

    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    cases = []
    for program in programs:
        status, detail, expected, actual = _run_case(program)
        counts[status] += 1
        cases.append({
            "name": str(program.relative_to(path if path.is_dir() else path.parent)),
            "status": status,
            "detail": detail,
            "expected": expected,
            "actual": actual,
        })
        if output_format == "text":
            print(f"{status}: {program}")
            if detail:
                print(f"  {detail}")
            if status == "FAIL":
                print("\n".join(difflib.unified_diff(
                    expected.splitlines(), actual.splitlines(),
                    fromfile="expected", tofile="actual", lineterm="",
                )))

    if output_format == "json":
        print(json.dumps({
            "path": str(path),
            "filter": filter_pattern,
            "counts": counts,
            "tests": cases,
        }, indent=2))
    else:
        print(
            f"Results: {counts['PASS']} passed, {counts['FAIL']} failed, "
            f"{counts['ERROR']} errored"
        )
    return 1 if counts["FAIL"] or counts["ERROR"] else 0
