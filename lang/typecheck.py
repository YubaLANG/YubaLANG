"""Conservative static type checks for values with statically known types."""

import ast
import re
import shlex

from .runtime import TYPES


_FUNCTION = re.compile(r"^func define ")
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def _literal_type(value: str) -> str | None:
    value = value.strip()
    if value.lower() in ("true", "false"):
        return "bool"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        try:
            return "string" if isinstance(ast.literal_eval(value), str) else None
        except (SyntaxError, ValueError):
            return None
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    if isinstance(parsed, bool):
        return "bool"
    if isinstance(parsed, int):
        return "int"
    if isinstance(parsed, float):
        return "float"
    if isinstance(parsed, list):
        return "list"
    if isinstance(parsed, dict):
        return "dict"
    if isinstance(parsed, set):
        return "set"
    if isinstance(parsed, tuple):
        return "tuple"
    return None


def _type_of(value: str, variables: dict[str, str | None]) -> str | None:
    value = value.strip()
    if value in variables:
        return variables[value]
    return _literal_type(value)


def _compatible(actual: str | None, expected: str) -> bool:
    return actual is None or actual == expected or (actual == "int" and expected == "float")


def _result_type(
    parts: list[str], variables: dict[str, str | None]
) -> tuple[str, str | None] | None:
    command = parts[0]
    fixed = {
        "all": ("bool", 2), "any": ("bool", 2), "ascii": ("string", 2),
        "bool": ("bool", 2), "bytearray": ("bytearray", 2), "bytes": ("bytes", 2),
        "callable": ("bool", 2), "chr": ("string", 2), "id": ("int", 2),
        "len": ("int", 2), "ord": ("int", 2), "repr": ("string", 2),
        "type": ("string", 2),
    }
    if command in fixed and len(parts) >= 3:
        result_type, destination_index = fixed[command]
        return parts[destination_index], result_type
    if command in ("enumerate", "filter", "map", "range", "reversed", "sorted", "zip"):
        if len(parts) >= 3:
            if command == "range":
                destination_index = {3: 2, 4: 3, 5: 3}.get(len(parts))
                if destination_index is not None:
                    return parts[destination_index], "list"
            if command in ("enumerate", "filter", "map"):
                return parts[3], "list"
            if command in ("reversed", "sorted"):
                return parts[2], "list"
            return parts[-1], "list"
    if command == "iter" and len(parts) == 3:
        return parts[2], "iterator"
    if command == "format" and len(parts) in (3, 4):
        return parts[-1], "string"
    if command == "compare" and len(parts) == 5:
        return parts[4], "bool"
    if command == "text" and len(parts) == 3 and parts[1] == "input":
        return parts[2], "string"
    if command == "list" and len(parts) == 4 and parts[1] == "len":
        return parts[3], "int"
    if command == "open" and len(parts) == 4:
        return parts[3], "file"
    if command == "record" and len(parts) >= 4 and parts[1] == "create":
        return parts[3], parts[2]
    if command == "slice" and len(parts) in (5, 6):
        return parts[4], variables.get(parts[1])
    if command == "ffi" and len(parts) >= 7 and "->" in parts:
        result_types = {"i32": "int", "i64": "int", "f64": "float", "bool": "bool"}
        if parts[4] in result_types:
            return parts[parts.index("->") + 1], result_types[parts[4]]
    if command == "func" and len(parts) >= 5 and parts[1] == "call" and "->" in parts:
        return parts[parts.index("->") + 1], None
    return None


def check_types(lines: list[str]) -> list[tuple[int, str]]:
    """Return (zero-based line, diagnostic) pairs for definite type mismatches."""
    diagnostics: list[tuple[int, str]] = []
    globals_: dict[str, str | None] = {}
    scopes = [globals_]
    record_types: dict[str, dict[str, str]] = {}
    function_depth = 0

    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parts = shlex.split(stripped, posix=False, comments=True)
        except ValueError:
            continue
        if not parts:
            continue
        if _FUNCTION.match(stripped):
            function_depth += 1
            scopes.append(dict(globals_))
            for parameter in parts[3:]:
                scopes[-1][parameter] = None
            continue
        if parts[0] == "endfunc" and function_depth:
            scopes.pop()
            function_depth -= 1
            continue
        variables = scopes[-1]
        if parts[0] == "record" and len(parts) >= 3 and parts[1] == "define":
            fields = {}
            for declaration in parts[3:]:
                if declaration.count(":") == 1:
                    field_name, field_type = declaration.split(":", 1)
                    fields[field_name] = field_type
            record_types[parts[2]] = fields
            continue
        if parts[0] == "record" and len(parts) >= 4 and parts[1] == "create":
            record_name, variable_name = parts[2], parts[3]
            fields = record_types.get(record_name)
            if fields is not None:
                values = parts[4:]
                if len(values) != len(fields):
                    diagnostics.append((
                        line_number,
                        f"Record '{record_name}' expects {len(fields)} field value(s), "
                        f"but got {len(values)}.",
                    ))
                for (field_name, expected), token in zip(fields.items(), values):
                    actual = _type_of(token, variables)
                    if actual is not None and not _compatible(actual, expected):
                        diagnostics.append((
                            line_number,
                            f"Type mismatch: field '{field_name}' requires '{expected}' "
                            f"but value has type '{actual}'.",
                        ))
                variables[variable_name] = record_name
            continue
        if (
            parts[0] == "define" and len(parts) >= 6 and parts[1] == "var"
            and parts[2].endswith(":") and parts[4] == "="
        ):
            name, declared = parts[2][:-1], parts[3]
            if declared not in TYPES and declared not in record_types:
                continue
            actual = _type_of(" ".join(parts[5:]), variables)
            if actual is not None and not _compatible(actual, declared):
                diagnostics.append((
                    line_number,
                    f"Type mismatch: variable '{name}' declares '{declared}' "
                    f"but its initial value has type '{actual}'.",
                ))
            variables[name] = declared
            continue

        if parts[0] == "convert":
            if len(parts) == 4 and parts[2] == "to" and parts[3] in TYPES:
                variables[parts[1]] = parts[3]
            elif len(parts) == 3 and parts[2] in TYPES:
                variables[parts[1]] = parts[2]
            continue
        if parts[0] == "assert":
            if len(parts) >= 2:
                condition_type = _type_of(parts[1], variables)
                if condition_type is not None and condition_type != "bool":
                    diagnostics.append((
                        line_number,
                        f"Type mismatch: assert condition has type '{condition_type}', "
                        "expected 'bool'.",
                    ))
            if len(parts) == 3:
                message_type = _type_of(parts[2], variables)
                if message_type is not None and message_type != "string":
                    diagnostics.append((
                        line_number,
                        f"Type mismatch: assert message has type '{message_type}', "
                        "expected 'string'.",
                    ))
            continue

        result = _result_type(parts, variables)
        if result is None:
            continue
        destination, actual = result
        expected = variables.get(destination)
        if actual is not None and expected is not None and not _compatible(actual, expected):
            diagnostics.append((
                line_number,
                f"Type mismatch: command result has type '{actual}' but destination "
                f"'{destination}' has type '{expected}'.",
            ))
        if destination not in variables and _IDENTIFIER.fullmatch(destination):
            variables[destination] = actual
    return diagnostics
