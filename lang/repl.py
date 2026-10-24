"""Interactive command loop for the YubaLANG interpreter."""

from collections.abc import Callable

from .interpreter import _split, execute_lines
from .runtime import Runtime


_OPEN_BLOCKS = {
    "if": "endif",
    "func": "endfunc",
    "loop": "endloop",
    "try": "endtry",
}


def run_repl(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    runtime = Runtime()
    lines: list[str] = []
    expected_closers: list[str] = []
    try:
        while True:
            prompt = "... " if expected_closers else "yl> "
            try:
                line = input_fn(prompt)
            except EOFError:
                if expected_closers:
                    output_fn(
                        f"Discarding incomplete block; expected {expected_closers[-1]}."
                    )
                return

            stripped = line.strip()
            if not expected_closers and stripped.lower() in ("exit", "quit"):
                return
            if not expected_closers and stripped.lower() == "reset":
                runtime.close_files()
                runtime = Runtime()
                output_fn("Session reset.")
                continue

            lines.append(line)
            try:
                parts = _split(line.strip())
            except SyntaxError:
                parts = []
            command = parts[0] if parts else ""
            if command == "func" and len(parts) >= 2 and parts[1] == "define":
                expected_closers.append(_OPEN_BLOCKS["func"])
            elif command == "if":
                expected_closers.append(_OPEN_BLOCKS["if"])
            elif command == "loop":
                expected_closers.append(_OPEN_BLOCKS["loop"])
            elif command == "try":
                expected_closers.append(_OPEN_BLOCKS["try"])
            elif expected_closers and command == expected_closers[-1]:
                expected_closers.pop()

            if expected_closers:
                continue
            try:
                execute_lines(lines, runtime, "<repl>")
            except SystemExit:
                pass
            finally:
                lines.clear()
    finally:
        runtime.close_files()
