import contextlib
import io
import unittest

from lang.interpreter import Runtime, execute_lines
from lang.typecheck import check_types


class LanguageConformanceTests(unittest.TestCase):
    def run_program(self, source: str) -> Runtime:
        runtime = Runtime()
        execute_lines(source.strip().splitlines(), runtime)
        return runtime

    def test_documented_expression_rules_and_boolean_conditions(self):
        runtime = self.run_program(
            """
            define var count: int = 2
            define var total: int = 0
            define var ok: bool = false
            set total = (count + 3) * 4 - 2
            compare total >= 18 ok
            if ok
                text output "ready"
            else
                text output "not-ready"
            endif
            """
        )

        self.assertEqual(runtime.require_var("total")["value"], 18)
        self.assertTrue(runtime.require_var("ok")["value"])

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                if 1
                    text output "bad"
                endif
                """
            )
        self.assertIn("Condition must evaluate to a boolean.", output.getvalue())

    def test_documented_function_rules_and_negative_cases(self):
        runtime = self.run_program(
            """
            func define add_one value:int -> int
                return value + 1
            endfunc
            define var result: int = 0
            func call add_one 4 -> result
            """
        )
        self.assertEqual(runtime.require_var("result")["value"], 5)

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                define var value: int = 0
                set value = "text"
                """
            )
        self.assertIn("Cannot assign", output.getvalue())

    def test_function_and_control_blocks_have_lexical_scopes(self):
        runtime = self.run_program(
            """
            define var value: int = 10
            if true
                define var value: int = 20
                set value = value + 1
                define var block_only: int = 1
            endif
            func define update
                define var value: int = 4
                if true
                    set value = value + 1
                    define var nested_only: int = 2
                endif
                return value
            endfunc
            define var result: int = 0
            func call update -> result
            """
        )

        self.assertEqual(runtime.require_var("value")["value"], 10)
        self.assertEqual(runtime.require_var("result")["value"], 5)
        self.assertIsNone(runtime.get_var("block_only"))
        self.assertIsNone(runtime.get_var("nested_only"))
        self.assertEqual(len(runtime.scopes), 1)

    def test_catch_and_loop_variables_do_not_leak_out_of_their_blocks(self):
        runtime = Runtime()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            execute_lines(
                [
                    "loop for 2",
                    "    define var temporary: int = 1",
                    "    set temporary = temporary + 1",
                    "endloop",
                    "try",
                    '    throw "handled"',
                    "catch problem",
                    "    text output problem",
                    "endtry",
                ],
                runtime,
            )

        self.assertEqual(output.getvalue(), "handled\n")
        self.assertIsNone(runtime.get_var("temporary"))
        self.assertIsNone(runtime.get_var("problem"))
        self.assertEqual(len(runtime.scopes), 1)

    def test_static_checker_uses_the_same_lexical_scope_rules(self):
        source = [
            'define var amount: string = ""',
            "if true",
            "    define var amount: int = 1",
            "    set amount = 2",
            "endif",
            'set amount = "done"',
        ]
        self.assertEqual(check_types(source), [])

    def test_function_calls_do_not_capture_callers_locals(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                func define read_secret
                    return secret
                endfunc
                func define caller
                    define var secret: int = 42
                    define var result: int = 0
                    func call read_secret -> result
                endfunc
                func call caller
                """
            )

        self.assertIn("Variable 'secret' is not defined.", output.getvalue())

    def test_closures_capture_live_bindings_and_survive_their_defining_call(self):
        runtime = self.run_program(
            """
            func define placeholder -> int
                return 0
            endfunc
            func define make_counter -> () -> int
                define var count: int = 0
                func define increment -> int
                    set count = count + 1
                    return count
                endfunc
                set count = 5
                return increment
            endfunc
            define var counter: ()->int = placeholder
            func call make_counter -> counter
            define var first: int = 0
            define var second: int = 0
            func call counter -> first
            func call counter -> second
            """
        )

        self.assertEqual(runtime.require_var("first")["value"], 6)
        self.assertEqual(runtime.require_var("second")["value"], 7)

    def test_nested_loop_blocks_match_their_own_end_commands(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_program(
                """
                loop for 2
                    loop for 2
                        text output "nested"
                    endloop
                endloop
                """
            )

        self.assertEqual(output.getvalue(), "nested\n" * 4)

    def test_builtins_and_source_located_errors_follow_documentation(self):
        runtime = self.run_program(
            """
            define var symbol: string = ""
            define var code: int = 9731
            chr code symbol
            define var size: int = 0
            len symbol size
            """
        )
        self.assertEqual(runtime.require_var("symbol")["value"], "\u2603")
        self.assertEqual(runtime.require_var("size")["value"], 1)

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.run_program(
                """
                define var count: int = 1
                define var text: string = ""
                list len count text
                """
            )
        self.assertIn("Variable 'count' is not of type 'list'.", output.getvalue())
        self.assertIn("list len count text", output.getvalue())


if __name__ == "__main__":
    unittest.main()
