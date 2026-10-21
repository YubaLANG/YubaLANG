"""Source-aware diagnostics for interpreted YubaLANG programs."""

import difflib
import re

from .runtime import Runtime, TYPES


_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
_UNDEFINED = re.compile(r"(?:Variable|Function) '([^']+)' is not defined\.")
_UNKNOWN_COMMAND = re.compile(r"Unknown command: ([A-Za-z_]\w*)")
_UNKNOWN_TYPE = re.compile(r"Unknown type: ([A-Za-z_]\w*)")

_COMMANDS = {
    "all", "any", "arith", "ascii", "bool", "break", "bytearray", "bytes",
    "callable", "chr", "compare", "continue", "convert", "define", "dict",
    "enumerate", "ffi", "filter", "format", "func", "getattr", "hasattr", "id",
    "if", "iter", "len", "list", "loop", "map", "next", "open", "ord",
    "range", "repr", "return", "reversed", "set", "setattr", "slice",
    "sorted", "text", "tuple", "type", "vars", "wait", "zip",
}


def _closest(name: str, candidates: set[str]) -> str | None:
    matches = difflib.get_close_matches(name, sorted(candidates), n=1, cutoff=0.65)
    return matches[0] if matches else None


def _context_hint(error: Exception, runtime: Runtime) -> str | None:
    message = str(error)
    match = _UNDEFINED.fullmatch(message)
    if match:
        name = match.group(1)
        candidates = (
            set(runtime.functions)
            if message.startswith("Function ")
            else {variable for scope in runtime.scopes for variable in scope}
        )
        suggestion = _closest(name, candidates)
        if suggestion:
            return f"Did you mean '{suggestion}'?"
        if message.startswith("Variable "):
            return "Check the variable name and make sure it is declared before use."
        return "Check the function name and make sure it is defined before use."

    match = _UNKNOWN_COMMAND.fullmatch(message)
    if match:
        suggestion = _closest(match.group(1), _COMMANDS)
        return f"Did you mean '{suggestion}'?" if suggestion else None

    match = _UNKNOWN_TYPE.fullmatch(message)
    if match:
        suggestion = _closest(match.group(1), set(TYPES))
        return f"Did you mean '{suggestion}'?" if suggestion else None

    if isinstance(error, ZeroDivisionError):
        return "Check that the divisor is not zero."
    if isinstance(error, IndexError):
        return "Check that the collection index is within its valid range."
    if isinstance(error, SyntaxError):
        return "Check the command syntax and its required arguments."
    return None


def format_diagnostic(
    error: Exception,
    source_name: str,
    line_number: int,
    source_line: str,
    runtime: Runtime,
) -> str:
    """Format an interpreter error with a source location and optional hint."""
    line = source_line.rstrip("\r\n")
    start = len(line) - len(line.lstrip())
    end = len(line.rstrip())
    message = str(error)

    match = _UNDEFINED.fullmatch(message)
    if match:
        name = match.group(1)
        token = next(
            (item for item in _IDENTIFIER.finditer(line, start, end) if item.group() == name),
            None,
        )
        if token:
            start, end = token.span()
    else:
        match = _UNKNOWN_COMMAND.fullmatch(message) or _UNKNOWN_TYPE.fullmatch(message)
        if match:
            token = next(
                (
                    item for item in _IDENTIFIER.finditer(line, start, end)
                    if item.group() == match.group(1)
                ),
                None,
            )
            if token:
                start, end = token.span()

    shown_line = line.expandtabs(4)
    start_column = len(line[:start].expandtabs(4))
    end_column = max(start_column + 1, len(line[:end].expandtabs(4)))
    output = [
        f"{source_name}:{line_number}:{start + 1}: error: {message}",
        f"  line {line_number}: {shown_line}",
        f"           {' ' * start_column}{'^' * (end_column - start_column)}",
    ]
    hint = _context_hint(error, runtime)
    if hint:
        output.append(f"  hint: {hint}")
    return "\n".join(output)
