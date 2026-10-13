import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lang.interpreter import Runtime, execute_lines, run_file


class BuiltinCommandTests(unittest.TestCase):
    def run_program(self, source: str) -> Runtime:
        runtime = Runtime()
        execute_lines(source.strip().splitlines(), runtime)
        return runtime

    def test_character_and_string_functions(self) -> None:
        runtime = self.run_program(
            """
            define var code: int = 9731
            define var symbol: string = ""
            define var point: int = 0
            define var escaped: string = ""
            define var shown: string = ""
            define var formatted: string = ""
            chr code symbol
            ord symbol point
            ascii symbol escaped
            repr symbol shown
            format code "04d" formatted
            """
        )
        self.assertEqual(runtime.require_var("symbol")["value"], "\u2603")
        self.assertEqual(runtime.require_var("point")["value"], 9731)
        self.assertEqual(runtime.require_var("escaped")["value"], "'\\u2603'")
        self.assertEqual(runtime.require_var("shown")["value"], "'\u2603'")
        self.assertEqual(runtime.require_var("formatted")["value"], "9731")

    def test_existing_commands_and_output_are_preserved(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_program(
                """
                define var number: int = 42
                define var enabled: bool = false
                define var numbers: list = [1, 2, 3]
                define var result: int = 0
                compare 10 > 5 enabled
                text output number
                text output enabled
                convert number to float
                text output number
                arith add 10 5
                arith sum numbers
                list append numbers 4
                list get numbers 3 result
                text output result
                func define greet
                    text output "Function works!"
                endfunc
                func call greet
                loop for 2
                    text output "Loop"
                endloop
                """
            )
        self.assertEqual(
            output.getvalue().splitlines(),
            ["42", "True", "42.0", "15", "6", "4", "Function works!", "Loop", "Loop"],
        )

    def test_collection_literals_resolve_variables_without_rewriting_strings(self) -> None:
        runtime = self.run_program(
            """
            define var value: int = 8
            define var values: list = [value, "true", -2]
            """
        )
        self.assertEqual(runtime.require_var("values")["value"], [8, "true", -2])

    def test_escaped_strings_are_decoded_for_output(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_program(
                r'''
                define var message: string = "first\nsecond"
                text output message
                text output "third\ttab"
                '''
            )
        self.assertEqual(output.getvalue().splitlines(), ["first", "second", "third\ttab"])

    def test_large_collections_and_numeric_edge_cases(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runtime = self.run_program(
                """
                define var values: list = []
                define var count: int = 0
                range 10000 values
                len values count
                arith sum values
                arith round 2.5
                arith round 3.5
                arith divmod -7 3
                arith pow 2 -3
                arith mod -7 3
                """
            )
        self.assertEqual(runtime.require_var("count")["value"], 10000)
        self.assertEqual(runtime.require_var("values")["value"][0], 0)
        self.assertEqual(runtime.require_var("values")["value"][-1], 9999)
        self.assertEqual(
            output.getvalue().splitlines(),
            ["49995000", "2", "4", "[-3, 2]", "0.125", "2"],
        )

    def test_command_error_includes_source_line(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                define var present: int = 1
                text output missing
                """
            )
        self.assertIn("Variable 'missing' is not defined.", output.getvalue())
        self.assertIn("line 2:", output.getvalue())
        self.assertIn("text output missing", output.getvalue())

    def test_existing_collection_and_utility_commands(self) -> None:
        runtime = self.run_program(
            """
            define var item: int = 5
            define var numbers: list = [1, 2]
            define var mapping: dict = {"a": item}
            define var values: set = {1, 2}
            define var pair: tuple = (7, 8)
            define var found: int = 0
            define var has_key: bool = false
            define var every: bool = false
            define var count: int = 0
            define var kind: string = ""
            define var data: bytes = "hello"
            dict get mapping "a" found
            dict set mapping "b" item
            getattr mapping "b" found
            hasattr mapping "missing" has_key
            setattr mapping "c" item
            set add values 3
            tuple get pair 1 found
            all numbers every
            len numbers count
            type numbers kind
            """
        )
        self.assertEqual(runtime.require_var("found")["value"], 8)
        self.assertFalse(runtime.require_var("has_key")["value"])
        self.assertTrue(runtime.require_var("every")["value"])
        self.assertEqual(runtime.require_var("count")["value"], 2)
        self.assertEqual(runtime.require_var("kind")["value"], "list")
        self.assertEqual(runtime.require_var("mapping")["value"], {"a": 5, "b": 5, "c": 5})
        self.assertEqual(runtime.require_var("values")["value"], {1, 2, 3})
        self.assertEqual(runtime.require_var("data")["value"], b"hello")

    def test_iteration_functions_and_empty_inputs(self) -> None:
        runtime = self.run_program(
            """
            define var values: list = [3, 1, 2]
            define var empty: list = []
            define var other: list = [1]
            define var indexed: list = []
            define var descending: list = []
            define var ranged: list = []
            define var sliced: list = []
            define var paired: list = []
            define var sorted_values: list = []
            enumerate values indexed 4
            reversed values descending
            range 1 6 ranged 2
            slice ranged 1 3 sliced
            sorted values sorted_values
            zip values ranged paired
            """
        )
        self.assertEqual(runtime.require_var("indexed")["value"], [(4, 3), (5, 1), (6, 2)])
        self.assertEqual(runtime.require_var("descending")["value"], [2, 1, 3])
        self.assertEqual(runtime.require_var("ranged")["value"], [1, 3, 5])
        self.assertEqual(runtime.require_var("sliced")["value"], [3, 5])
        self.assertEqual(runtime.require_var("sorted_values")["value"], [1, 2, 3])
        self.assertEqual(runtime.require_var("paired")["value"], [(3, 1), (1, 3), (2, 5)])
        self.assertEqual(runtime.require_var("empty")["value"], [])

    def test_iter_next_map_and_filter_with_user_function(self) -> None:
        runtime = self.run_program(
            """
            func define is_positive value
                define var result: bool = false
                compare value > 0 result
                return result
            endfunc
            define var values: list = [-2, 0, 5]
            define var positives: list = []
            define var magnitudes: list = []
            define var current: int = 0
            filter is_positive values positives
            map abs values magnitudes
            iter positives cursor
            next cursor current
            """
        )
        self.assertEqual(runtime.require_var("positives")["value"], [5])
        self.assertEqual(runtime.require_var("magnitudes")["value"], [2, 0, 5])
        self.assertEqual(runtime.require_var("current")["value"], 5)
        self.assertEqual(runtime.require_var("cursor")["type"], "iterator")

    def test_function_arguments_return_and_next_default(self) -> None:
        runtime = self.run_program(
            """
            func define identity item
                return item
            endfunc
            func define nested item
                define var result: int = 0
                func call identity item -> result
                return result
            endfunc
            define var source: list = [7]
            define var mapped: list = []
            define var answer: int = 0
            define var fallback: int = -1
            map identity source mapped
            iter source cursor
            next cursor answer
            next cursor fallback -1
            func call nested 12 -> answer
            """
        )
        self.assertEqual(runtime.require_var("mapped")["value"], [7])
        self.assertEqual(runtime.require_var("fallback")["value"], -1)
        self.assertEqual(runtime.require_var("answer")["value"], 12)

    def test_empty_inputs_and_numeric_edges(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runtime = self.run_program(
                """
                define var empty: list = []
                define var enumerated: list = []
                define var reverse_values: list = []
                define var sorted_values: list = []
                define var paired: list = []
                define var transformed: list = []
                define var bounded: list = []
                enumerate empty enumerated
                reversed empty reverse_values
                sorted empty sorted_values
                zip empty other paired
                map abs empty transformed
                range 3 3 bounded
                arith pow 2 8
                arith divmod 7 3
                """
            )
        self.assertEqual(runtime.require_var("enumerated")["value"], [])
        self.assertEqual(runtime.require_var("reverse_values")["value"], [])
        self.assertEqual(runtime.require_var("sorted_values")["value"], [])
        self.assertEqual(runtime.require_var("paired")["value"], [])
        self.assertEqual(runtime.require_var("transformed")["value"], [])
        self.assertEqual(runtime.require_var("bounded")["value"], [])
        self.assertEqual(output.getvalue().splitlines(), ["256", "[2, 1]"])

    def test_invalid_type_conversion_is_reported(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                define var value: string = "not-a-number"
                convert value to int
                """
            )
        self.assertIn("Cannot convert 'value' to int", output.getvalue())

    def test_function_argument_count_is_reported(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                func define expects_one value
                    return value
                endfunc
                func call expects_one
                """
            )
        self.assertIn("expects 1 argument(s), but got 0", output.getvalue())

    def test_run_file_reads_and_executes_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "program.hl"
            opened_file = Path(directory) / "opened.txt"
            escaped_path = str(opened_file).replace("\\", "\\\\")
            source.write_text(
                f'define var message: string = "from file"\n'
                f'open "{escaped_path}" "w" handle\n'
                "text output message\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_file(str(source))
            self.assertTrue(opened_file.exists())
            opened_file.unlink()
        self.assertEqual(output.getvalue().splitlines(), ["from file"])

    def test_invalid_chr_reports_runtime_error(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                define var character: string = ""
                chr 1114112 character
                """
            )
        self.assertIn("chr() arg not in range", output.getvalue())


if __name__ == "__main__":
    unittest.main()
