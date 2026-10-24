import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lang.interpreter import _split_cached, execute_lines, run_file
from lang.typecheck import check_types


class RuntimeDiagnosticTests(unittest.TestCase):
    def test_file_diagnostic_includes_location_snippet_and_variable_suggestion(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "example.yl"
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
            source = Path(directory) / "bom.yl"
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
            execute_lines(source, source_name="nested.yl")

        diagnostic = output.getvalue()
        self.assertIn("nested.yl:3:17: error:", diagnostic)
        self.assertIn("Did you mean 'count'?", diagnostic)

    def test_unknown_command_suggests_a_valid_command(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["tex output 'hello'"], source_name="typo.yl")

        self.assertIn("typo.yl:1:1: error: Unknown command: tex", output.getvalue())
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
            execute_lines(source, source_name="function.yl")

        self.assertIn("Function 'calculte' is not defined.", output.getvalue())
        self.assertIn("Did you mean 'calculate'?", output.getvalue())

    def test_syntax_error_has_location_and_actionable_hint(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["if true", "text output 'unfinished"], source_name="syntax.yl")

        diagnostic = output.getvalue()
        self.assertIn("syntax.yl:2:1: error: Invalid command quoting:", diagnostic)
        self.assertIn("line 2: text output 'unfinished", diagnostic)
        self.assertIn("Check the command syntax", diagnostic)

    def test_recursive_function_limit_has_a_source_diagnostic(self):
        output = io.StringIO()
        source = [
            "func define recurse",
            "    func call recurse",
            "endfunc",
            "func call recurse",
        ]

        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(source, source_name="recursion.yl")

        diagnostic = output.getvalue()
        self.assertIn("Maximum function call depth (128) exceeded.", diagnostic)
        self.assertIn("hint: Check that recursive functions eventually reach a stopping condition.", diagnostic)
        self.assertNotIn("Traceback", diagnostic)

    def test_command_tokenization_cache_reuses_immutable_results(self):
        _split_cached.cache_clear()
        with mock.patch(
            "lang.interpreter.shlex.split",
            return_value=["text", "output", "ok"],
        ) as split:
            first = _split_cached("text output ok")
            second = _split_cached("text output ok")
        self.assertEqual(first, ("text", "output", "ok"))
        self.assertEqual(second, first)
        self.assertIs(first, second)
        split.assert_called_once()
        _split_cached.cache_clear()

    def test_memory_exhaustion_has_a_source_diagnostic(self):
        output = io.StringIO()
        with mock.patch("lang.interpreter.execute_command", side_effect=MemoryError):
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(["text output 'hello'"], source_name="large.yl")

        self.assertIn("large.yl:1:1: error:", output.getvalue())
        self.assertIn("Reduce the size of collections", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_uncaught_language_exception_has_original_location_and_stack(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "func define fail",
                    '    throw "broken"',
                    "endfunc",
                    "func call fail",
                ],
                source_name="exceptions.yl",
            )
        self.assertIn("exceptions.yl:2:5: error: Uncaught language exception: broken", output.getvalue())
        self.assertIn("at fail (exceptions.yl:4)", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_finally_runs_before_an_uncaught_exception_exits(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "try",
                    '    throw "failure"',
                    "finally",
                    '    text output "cleanup"',
                    "endtry",
                ],
                source_name="finally.yl",
            )
        diagnostic = output.getvalue()
        self.assertIn("finally.yl:2:5: error: Uncaught language exception: failure", diagnostic)
        self.assertIn("cleanup", diagnostic)

    def test_cli_reports_source_error_without_python_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "broken.yl"
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

    def test_cli_type_check_reports_definite_mismatch_without_running(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "type_error.yl"
            source.write_text(
                'define var label: string = ""\n'
                "define var values: list = [1, 2]\n"
                "list len values label\n"
                'text output "must not execute"\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "YubaLANG.py", "check", str(source)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{source}:3:1: error: Type mismatch:", result.stdout)
        self.assertNotIn("must not execute", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_static_checker_infers_generic_and_function_types(self):
        diagnostics = check_types(
            [
                "func define increment value:int -> int",
                "    return value",
                "endfunc",
                "define var transform: (int)->int = increment",
                'define var result: string = ""',
                "func call transform 5 -> result",
                'define var values: list[int] = [1, "bad"]',
                "define var optional: int? = none",
                "func define invalid value:int -> int",
                "    return 'bad'",
                "endfunc",
                'func call increment "bad"',
            ]
        )
        self.assertEqual([line for line, _ in diagnostics], [5, 6, 9, 11])
        self.assertIn("command result has type 'int'", diagnostics[0][1])
        self.assertIn("list[int | string]", diagnostics[1][1])
        self.assertIn("function return has type 'string'", diagnostics[2][1])
        self.assertIn("parameter requires 'int'", diagnostics[3][1])


if __name__ == "__main__":
    unittest.main()
