import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.interpreter import execute_lines, run_file


class RuntimeDiagnosticTests(unittest.TestCase):
    def test_file_diagnostic_includes_location_snippet_and_variable_suggestion(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "example.hl"
            source.write_text(
                "define var count: int = 1\n"
                "text output coutn\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                run_file(str(source))

        diagnostic = output.getvalue()
        self.assertIn(f"{source}:2:13: error: Variable 'coutn' is not defined.", diagnostic)
        self.assertIn("line 2: text output coutn", diagnostic)
        self.assertIn("^^^^^", diagnostic)
        self.assertIn("Did you mean 'count'?", diagnostic)
        self.assertNotIn("Traceback", diagnostic)

    def test_run_file_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bom.hl"
            source.write_text("text output 'hello'\n", encoding="utf-8-sig")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_file(str(source))

        self.assertEqual(output.getvalue(), "hello\n")

    def test_function_error_keeps_original_source_line(self):
        output = io.StringIO()
        source = [
            "define var count: int = 1",
            "func define calculate",
            "    text output coutn",
            "endfunc",
            "func call calculate",
        ]

        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(source, source_name="nested.hl")

        diagnostic = output.getvalue()
        self.assertIn("nested.hl:3:17: error:", diagnostic)
        self.assertIn("Did you mean 'count'?", diagnostic)

    def test_unknown_command_suggests_a_valid_command(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["tex output 'hello'"], source_name="typo.hl")

        self.assertIn("typo.hl:1:1: error: Unknown command: tex", output.getvalue())
        self.assertIn("Did you mean 'text'?", output.getvalue())

    def test_undefined_function_suggests_a_defined_function(self):
        output = io.StringIO()
        source = [
            "func define calculate",
            "    return 1",
            "endfunc",
            "func call calculte",
        ]

        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(source, source_name="function.hl")

        self.assertIn("Function 'calculte' is not defined.", output.getvalue())
        self.assertIn("Did you mean 'calculate'?", output.getvalue())

    def test_syntax_error_has_location_and_actionable_hint(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["if true", "text output 'unfinished"], source_name="syntax.hl")

        diagnostic = output.getvalue()
        self.assertIn("syntax.hl:2:1: error: Invalid command quoting:", diagnostic)
        self.assertIn("line 2: text output 'unfinished", diagnostic)
        self.assertIn("Check the command syntax", diagnostic)

    def test_cli_reports_source_error_without_python_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "broken.hl"
            source.write_text("text output missing\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "YubaLANG.py", str(source)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{source}:1:", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
