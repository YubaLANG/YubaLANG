"""Formatting utilities for YubaLANG source files."""

import shlex


class FormatError(ValueError):
    """Raised when source structure cannot be formatted safely."""


def format_source(source: str) -> str:
    """Return source formatted with four-space block indentation and one final newline."""
    blocks: list[tuple[str, int]] = []
    formatted: list[str] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        content = line.strip()
        if not content:
            formatted.append("")
            continue

        try:
            parts = shlex.split(content, posix=False, comments=True)
        except ValueError as error:
            raise FormatError(f"line {line_number}: invalid command quoting: {error}") from error

        command = parts[0] if parts else ""
        is_exact_end = content in ("endfunc", "endloop", "endtry")
        closing = command if command == "endif" or is_exact_end else ""

        if command in ("else", "elseif", "catch", "finally"):
            expected = "try" if command in ("catch", "finally") else "if"
            if not blocks or blocks[-1][0] != expected:
                raise FormatError(f"line {line_number}: {command} without a matching {expected}")

        if closing:
            expected = {
                "endif": "if", "endfunc": "func", "endloop": "loop", "endtry": "try",
            }[closing]
            if not blocks or blocks[-1][0] != expected:
                raise FormatError(f"line {line_number}: {closing} without a matching block")
            blocks.pop()

        indent = len(blocks) - int(command in ("else", "elseif", "catch", "finally"))
        formatted.append("    " * max(indent, 0) + content)

        if command == "if":
            blocks.append(("if", line_number))
        elif command == "func" and len(parts) >= 3 and parts[1] == "define":
            blocks.append(("func", line_number))
        elif command == "loop" and len(parts) == 3 and parts[1] in ("for", "while"):
            blocks.append(("loop", line_number))
        elif command == "try":
            blocks.append(("try", line_number))

    if blocks:
        block, line_number = blocks[-1]
        ending = {"if": "endif", "func": "endfunc", "loop": "endloop", "try": "endtry"}[block]
        raise FormatError(f"line {line_number}: missing {ending}")

    return "\n".join(formatted).rstrip("\n") + "\n"
