import contextlib
import io
import unittest

from lang.expressions import evaluate_expression, parse_expression
from lang.interpreter import Runtime, execute_lines
from lang.lsp import analyze_document
from lang.syntax import parse_program


class ExpressionTests(unittest.TestCase):
    def test_precedence_parentheses_and_associativity(self):
        runtime = Runtime()
        self.assertEqual(evaluate_expression("1 + 2 * 3", runtime), 7)
        self.assertEqual(evaluate_expression("(1 + 2) * 3", runtime), 9)
        self.assertEqual(evaluate_expression("2 ** 3 ** 2", runtime), 512)
        self.assertEqual(evaluate_expression("-2 ** 2", runtime), -4)

    def test_boolean_operators_short_circuit_and_require_booleans(self):
        runtime = Runtime()
        self.assertFalse(evaluate_expression("false and missing", runtime))
        self.assertTrue(evaluate_expression("true or missing", runtime))
        with self.assertRaisesRegex(TypeError, "boolean operands"):
            evaluate_expression("1 and true", runtime)

    def test_only_supported_expression_syntax_is_accepted(self):
        for source in ("f()", "[x for x in values]", "1 if true else 0", "x.y"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse_expression(source)

    def test_command_parser_keeps_source_locations(self):
        nodes = parse_program(
            ["", "    text output value # comment"],
            source_name="sample.yl",
            line_numbers=[10, 11],
        )
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].tokens, ("text", "output", "value"))
        self.assertEqual(nodes[0].location.source_name, "sample.yl")
        self.assertEqual(nodes[0].location.line, 11)
        self.assertEqual(nodes[0].location.column, 5)

    def test_declarations_assignment_output_comparisons_and_returns(self):
        output = io.StringIO()
        source = [
            "define var base: int = 2",
            "define var result: int = base * 3 + 1",
            "set result = (result - 1) ** 2",
            "text output result",
            "define var passed: bool = false",
            "compare result >= 36 and not false passed",
            "if passed",
            "    text output 'passed'",
            "endif",
            "func define calculate value:int -> int",
            "    return value * value",
            "endfunc",
            "define var square: int = 0",
            "func call calculate 5 -> square",
            "text output square",
        ]
        with contextlib.redirect_stdout(output):
            execute_lines(source, source_name="expressions.yl")

        self.assertEqual(output.getvalue(), "36\npassed\n25\n")

    def test_assignment_enforces_declared_type_and_existing_target(self):
        for source, message in (
            (["define var count: int = 1", "set count = true"], "Cannot assign"),
            (["set count = 1"], "is not defined"),
        ):
            output = io.StringIO()
            with self.subTest(source=source):
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                    execute_lines(source, source_name="assignment.yl")
            self.assertIn(message, output.getvalue())

    def test_control_conditions_must_be_boolean(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["if 1", "endif"], source_name="condition.yl")
        self.assertIn("Condition must evaluate to a boolean.", output.getvalue())

    def test_language_server_parses_new_expression_forms(self):
        self.assertEqual(
            analyze_document(
                "define var value: int = 0\n"
                "set value = (2 + 3) * 4\n"
                "if value >= 20 and not false\n"
                "    text output value\n"
                "endif\n"
            ),
            [],
        )
        diagnostics = analyze_document(
            "define var value: int = 0\n"
            "set value = open('file')\n"
        )
        self.assertTrue(any("Unsupported syntax" in item["message"] for item in diagnostics))

    def test_static_checker_infers_expression_results(self):
        diagnostics = analyze_document(
            "define var count: int = 1\n"
            "set count = count + 2\n"
            "define var label: string = ''\n"
            "set label = count * 2\n"
            "if count\n"
            "endif\n"
        )
        messages = [item["message"] for item in diagnostics]
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("assignment has type 'int'" in item for item in messages))
        self.assertTrue(any("condition has type 'int'" in item for item in messages))


if __name__ == "__main__":
    unittest.main()
