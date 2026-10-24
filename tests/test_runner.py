import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, str(ENTRY_POINT), *map(str, arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class TestRunnerTests(unittest.TestCase):
    def test_discovers_and_passes_output_fixture(self):
        result = run_cli("test", REPOSITORY_ROOT / "tests" / "cases")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertIn("Results: 1 passed, 0 failed, 0 errored", result.stdout)

    def test_accepts_relative_test_directory(self):
        result = run_cli("test", "tests/cases")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Results: 1 passed, 0 failed, 0 errored", result.stdout)

    def test_getting_started_example_matches_its_expected_output(self):
        example = REPOSITORY_ROOT / "examples" / "getting-started.yl"
        result = run_cli("test", example)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Results: 1 passed, 0 failed, 0 errored", result.stdout)

    def test_reports_output_mismatch_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "wrong.yl").write_text('text output "actual"\n', encoding="utf-8")
            (folder / "wrong.expected.txt").write_text("expected\n", encoding="utf-8")

            result = run_cli("test", folder)

        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL:", result.stdout)
        self.assertIn("expected 'expected', got 'actual'", result.stdout)
        self.assertIn("Results: 0 passed, 1 failed, 0 errored", result.stdout)

    def test_requires_exact_final_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "newline.yl").write_text('text output "same"\n', encoding="utf-8")
            (folder / "newline.expected.txt").write_text("same", encoding="utf-8")

            result = run_cli("test", folder)

        self.assertEqual(result.returncode, 1)
        self.assertIn("trailing newline differs", result.stdout)

    def test_reports_runtime_error(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "broken.yl").write_text("text output missing\n", encoding="utf-8")
            (folder / "broken.expected.txt").write_text("", encoding="utf-8")

            result = run_cli("test", folder)

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stdout)
        self.assertIn("Variable 'missing' is not defined.", result.stdout)

    def test_empty_directory_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli("test", directory)

        self.assertEqual(result.returncode, 1)
        self.assertIn("no .yl tests found", result.stderr)

    def test_missing_expected_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "missing-output.yl"
            program.write_text('text output "hello"\n', encoding="utf-8")

            result = run_cli("test", program)

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing expected-output file", result.stdout)

    def test_filter_selects_test_names(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "alpha.yl").write_text('text output "alpha"\n', encoding="utf-8")
            (folder / "alpha.expected.txt").write_text("alpha\n", encoding="utf-8")
            (folder / "beta.yl").write_text('text output "beta"\n', encoding="utf-8")
            (folder / "beta.expected.txt").write_text("beta\n", encoding="utf-8")
            result = run_cli("test", "--filter", "bet", folder)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Results: 1 passed, 0 failed, 0 errored", result.stdout)
        self.assertIn("beta.yl", result.stdout)
        self.assertNotIn("alpha.yl", result.stdout)

    def test_json_output_contains_structured_results(self):
        result = run_cli("test", "--json", REPOSITORY_ROOT / "tests" / "cases")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["counts"]["PASS"], 1)
        self.assertEqual(report["tests"][0]["status"], "PASS")

    def test_failure_outputs_unified_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "wrong.yl").write_text('text output "actual"\n', encoding="utf-8")
            (folder / "wrong.expected.txt").write_text("expected\n", encoding="utf-8")
            result = run_cli("test", folder)

        self.assertIn("--- expected", result.stdout)
        self.assertIn("+++ actual", result.stdout)
        self.assertIn("-expected", result.stdout)
        self.assertIn("+actual", result.stdout)


if __name__ == "__main__":
    unittest.main()
