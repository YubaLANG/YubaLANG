import unittest

from lang.debugger import DebugEvent, Debugger
from lang.interpreter import execute_lines
from lang.runtime import Runtime


class DebuggerTests(unittest.TestCase):
    def test_breakpoints_expose_stack_and_visible_variables(self):
        events: list[DebugEvent] = []
        debugger = Debugger(events.append)
        debugger.add_breakpoint(3, "<memory>")
        runtime = Runtime(debugger=debugger)

        execute_lines(
            [
                "define var count: int = 0",
                "func define increment",
                "    set count = count + 1",
                "endfunc",
                "func call increment",
                "set count = count",
            ],
            runtime,
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.reason, "breakpoint")
        self.assertEqual((event.source_name, event.line_number), ("<memory>", 3))
        self.assertEqual(event.function_depth, 1)
        self.assertEqual(event.stack[-1].function, "increment")
        self.assertEqual(event.variables["count"], 0)
        with self.assertRaises(TypeError):
            event.variables["count"] = 10
        self.assertEqual(runtime.require_var("count")["value"], 1)

    def test_step_out_stops_at_the_callers_next_statement(self):
        events: list[DebugEvent] = []
        debugger = Debugger(
            lambda event: (
                events.append(event),
                debugger.step_out() if event.line_number == 3 else None,
            )
        )
        debugger.add_breakpoint(3)
        runtime = Runtime(debugger=debugger)

        execute_lines(
            [
                "define var count: int = 0",
                "func define increment",
                "    set count = count + 1",
                "endfunc",
                "func call increment",
                "set count = count",
            ],
            runtime,
        )

        self.assertEqual(
            [(event.line_number, event.function_depth) for event in events],
            [(3, 1), (6, 0)],
        )
        self.assertEqual(events[-1].variables["count"], 1)

    def test_step_into_and_step_over(self):
        events: list[DebugEvent] = []
        runtime = Runtime()

        def on_stop(event: DebugEvent) -> None:
            events.append(event)
            if event.line_number == 1:
                debugger.step_over()
            elif event.line_number == 4:
                debugger.step_into()

        debugger = Debugger(on_stop)
        runtime.debugger = debugger
        debugger.step_into()
        execute_lines(
            [
                "func define increment",
                "    return 1",
                "endfunc",
                "func call increment",
                "define var done: bool = true",
            ],
            runtime,
        )

        self.assertEqual(
            [(event.line_number, event.function_depth) for event in events],
            [(1, 0), (4, 0), (2, 1)],
        )

    def test_breakpoint_validation_and_removal(self):
        debugger = Debugger(lambda _event: None)
        with self.assertRaises(ValueError):
            debugger.add_breakpoint(0)
        debugger.add_breakpoint(4, "main.yl")
        self.assertTrue(debugger.remove_breakpoint(4, "main.yl"))
        self.assertFalse(debugger.remove_breakpoint(4, "main.yl"))


if __name__ == "__main__":
    unittest.main()
