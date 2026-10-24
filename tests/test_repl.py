import contextlib
import io
import unittest

from lang.repl import run_repl


class ReplTests(unittest.TestCase):
    def test_repl_keeps_state_and_accepts_multiline_functions(self):
        entries = iter([
            "define var count: int = 2",
            "func define doubled value",
            "return 4",
            "endfunc",
            "func call doubled count -> count",
            "text output count",
            "exit",
        ])
        prompts = []
        output = io.StringIO()

        def input_fn(prompt):
            prompts.append(prompt)
            return next(entries)

        with contextlib.redirect_stdout(output):
            run_repl(input_fn)

        self.assertIn("4\n", output.getvalue())
        self.assertIn("... ", prompts)

    def test_repl_reset_discards_session_state(self):
        entries = iter([
            "define var value: int = 7",
            "reset",
            "text output value",
            "quit",
        ])
        output = io.StringIO()

        def input_fn(_prompt):
            return next(entries)

        with contextlib.redirect_stdout(output):
            run_repl(input_fn)

        self.assertIn("Session reset.", output.getvalue())
        self.assertIn("Variable 'value' is not defined.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
