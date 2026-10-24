import ast
from typing import Any

from .runtime import Runtime


def resolve(value: str, runtime: Runtime) -> Any:
    variable = runtime.get_var(value)
    if variable is not None:
        return variable["value"]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        try:
            result = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"Invalid string literal: {error}") from error
        if not isinstance(result, str):
            raise ValueError("Expected a string literal.")
        return result
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lower() == "none":
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        pass
    return value


def ascii_value(value: Any) -> str:
    return ascii(value)


def character(codepoint: Any) -> str:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("chr() requires an integer.")
    try:
        return chr(codepoint)
    except ValueError as error:
        raise ValueError(f"chr() arg not in range(0x110000): {codepoint}") from error


def ordinal(value: Any) -> int:
    if not isinstance(value, str) or len(value) != 1:
        raise TypeError("ord() expected a single character string.")
    return ord(value)


def format_value(value: Any, spec: str) -> str:
    try:
        return format(value, spec)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Cannot format value with format specifier '{spec}': {error}") from error


def representation(value: Any) -> str:
    return repr(value)
