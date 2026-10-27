import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lang.interpreter import Runtime, execute_lines, run_file


class ImportTests(unittest.TestCase):
    def test_module_private_functions_remain_callable_from_public_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.yl").write_text(
                "func private define helper -> string\n"
                '    return "hidden"\n'
                "endfunc\n"
                "func define answer -> string\n"
                '    define var value: string = ""\n'
                "    func call helper -> value\n"
                "    return value\n"
                "endfunc\n",
                encoding="utf-8",
            )
            runtime = Runtime()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                execute_lines(
                    [
                        "import library",
                        'define var result: string = ""',
                        "func call library.answer -> result",
                        "text output result",
                    ],
                    runtime,
                    str(root / "main.yl"),
                )

            self.assertEqual(output.getvalue(), "hidden\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(
                    ["func call library.helper"],
                    runtime,
                    str(root / "main.yl"),
                )

        self.assertIn("is private to its module", output.getvalue())

    def test_module_variables_remain_global_when_imported_from_a_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.yl").write_text(
                "define var module_value: int = 42\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                execute_lines(
                    [
                        "if true",
                        "    import library",
                        "endif",
                        "text output module_value",
                    ],
                    Runtime(),
                    str(root / "main.yl"),
                )

        self.assertEqual(output.getvalue(), "42\n")

    def test_import_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.yl").write_text(
                "func define answer\n    return 42\nendfunc\n",
                encoding="utf-8-sig",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                execute_lines(
                    [
                        "import library",
                        "define var result: int = 0",
                        "func call library.answer -> result",
                        "text output result",
                    ],
                    Runtime(),
                    str(root / "main.yl"),
                )

        self.assertEqual(output.getvalue(), "42\n")

    def test_imports_and_calls_namespaced_functions_with_private_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mathlib.yl").write_text(
                "func define helper\n"
                "    return 42\n"
                "endfunc\n"
                "func define answer\n"
                "    define var result: int = 0\n"
                "    func call helper -> result\n"
                "    return result\n"
                "endfunc\n"
                "func call helper\n",
                encoding="utf-8",
            )
            program = root / "main.yl"
            program.write_text(
                "import mathlib as math\n"
                "define var result: int = 0\n"
                "func call math.answer -> result\n"
                "text output result\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_file(str(program))

        self.assertEqual(output.getvalue(), "42\n")

    def test_imported_function_is_available_to_callable_and_map(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "helpers.yl").write_text(
                "func define identity value\n"
                "    return value\n"
                "endfunc\n",
                encoding="utf-8",
            )
            runtime = Runtime()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                execute_lines(
                    [
                        "import helpers",
                        "define var is_callable: bool = false",
                        "callable helpers.identity is_callable",
                        "define var values: list = [1, 2]",
                        "define var mapped: list = []",
                        "map helpers.identity values mapped",
                    ],
                    runtime,
                    str(root / "main.yl"),
                )

        self.assertTrue(runtime.require_var("is_callable")["value"])
        self.assertEqual(runtime.require_var("mapped")["value"], [1, 2])

    def test_reuses_module_import_and_reports_missing_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.yl").write_text(
                "func define value\n    return 1\nendfunc\n",
                encoding="utf-8",
            )
            runtime = Runtime()
            execute_lines(
                ["import library", "import library", "import library as helpers"],
                runtime,
                str(root / "main.yl"),
            )
            self.assertEqual(len(runtime.loaded_modules), 1)
            self.assertEqual(runtime.module_aliases["helpers"], "library")

            (root / "other.yl").write_text(
                "func define different\n    return 2\nendfunc\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(
                    ["import other as library"],
                    runtime,
                    str(root / "main.yl"),
                )
            self.assertIn("already bound to a different module", output.getvalue())

            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(
                    ["import missing"],
                    Runtime(),
                    str(root / "main.yl"),
                )
            self.assertIn("Module 'missing' was not found", output.getvalue())

            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(
                    ["import libray"],
                    Runtime(),
                    str(root / "main.yl"),
                )
            self.assertIn(f"{root / 'main.yl'}:1:8: error:", output.getvalue())
            self.assertIn("Did you mean 'library'?", output.getvalue())

    def test_reports_import_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.yl").write_text("import second\n", encoding="utf-8")
            (root / "second.yl").write_text("import first\n", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(["import first"], Runtime(), str(root / "main.yl"))

        self.assertIn("Import cycle detected", output.getvalue())


if __name__ == "__main__":
    unittest.main()
