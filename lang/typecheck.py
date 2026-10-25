"""Conservative static type checks for values with statically known types."""

import ast
import re

from .runtime import TYPES
from .syntax import tokenize_line
from .type_system import TypeSpec, format_type, is_known_type, parse_type


_FUNCTION = re.compile(r"^func define ")
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def _literal_type(value: str) -> str | None:
    value = value.strip()
    try:
        parsed = ast.literal_eval(_normalize_literals(value))
    except (SyntaxError, ValueError):
        return None
    return _python_type(parsed)


def _normalize_literals(value: str) -> str:
    result = []
    quote = None
    escaped = False
    index = 0
    replacements = {"true": "True", "false": "False", "none": "None"}
    while index < len(value):
        char = value[index]
        if quote is not None:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            result.append(char)
            index += 1
            continue
        match = re.match(r"[A-Za-z_]\w*", value[index:])
        if match:
            token = match.group()
            before = value[index - 1] if index else ""
            after_index = index + len(token)
            after = value[after_index] if after_index < len(value) else ""
            if token.lower() in replacements and not (
                before.isalnum() or before == "_" or after.isalnum() or after == "_"
            ):
                token = replacements[token.lower()]
            result.append(token)
            index = after_index
        else:
            result.append(char)
            index += 1
    return "".join(result)


def _merge_types(types: list[str]) -> str | None:
    if not types:
        return None
    options = []
    for type_name in types:
        spec = parse_type(type_name)
        options.extend(spec.arguments if spec.name == "union" else (spec,))
    return format_type(TypeSpec("union", tuple(dict.fromkeys(options))))


def _python_type(value: object) -> str | None:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        item_types = [_python_type(item) for item in value]
        item_type = _merge_types([item for item in item_types if item])
        return f"list[{item_type}]" if item_type else "list"
    if isinstance(value, set):
        item_types = [_python_type(item) for item in value]
        item_type = _merge_types([item for item in item_types if item])
        return f"set[{item_type}]" if item_type else "set"
    if isinstance(value, dict):
        key_types = [_python_type(item) for item in value]
        item_types = [_python_type(item) for item in value.values()]
        key_type = _merge_types([item for item in key_types if item])
        value_type = _merge_types([item for item in item_types if item])
        return f"dict[{key_type}, {value_type}]" if key_type and value_type else "dict"
    if isinstance(value, tuple):
        item_types = [_python_type(item) for item in value]
        return (
            f"tuple[{', '.join(item_types)}]"
            if item_types and all(item_types)
            else "tuple"
        )
    return None


def _type_of(
    value: str,
    variables: dict[str, str | None],
    functions: dict[str, str | None] | None = None,
) -> str | None:
    value = value.strip()
    if value in variables:
        return variables[value]
    if functions and value in functions:
        return functions[value]
    return _expression_type(value, variables, functions)


def _expression_type(
    source: str,
    variables: dict[str, str | None],
    functions: dict[str, str | None] | None,
) -> str | None:
    try:
        expression = ast.parse(_normalize_literals(source), mode="eval").body
    except SyntaxError:
        return None

    def infer(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant):
            return _python_type(node.value)
        if isinstance(node, ast.Name):
            return variables.get(node.id) or (functions or {}).get(node.id)
        if isinstance(node, ast.List):
            item_types = [infer(item) for item in node.elts]
            merged = _merge_types([item for item in item_types if item])
            return f"list[{merged}]" if merged else "list"
        if isinstance(node, ast.Set):
            item_types = [infer(item) for item in node.elts]
            merged = _merge_types([item for item in item_types if item])
            return f"set[{merged}]" if merged else "set"
        if isinstance(node, ast.Tuple):
            item_types = [infer(item) for item in node.elts]
            return (
                f"tuple[{', '.join(item_types)}]"
                if item_types and all(item_types) else "tuple"
            )
        if isinstance(node, ast.Dict):
            key_types = [infer(item) for item in node.keys if item is not None]
            value_types = [infer(item) for item in node.values]
            key_type = _merge_types([item for item in key_types if item])
            value_type = _merge_types([item for item in value_types if item])
            return (
                f"dict[{key_type}, {value_type}]"
                if key_type and value_type else "dict"
            )
        if isinstance(node, ast.UnaryOp):
            operand = infer(node.operand)
            if isinstance(node.op, ast.Not):
                return "bool" if operand == "bool" else None
            return operand if operand in ("int", "float") else None
        if isinstance(node, ast.BinOp):
            left, right = infer(node.left), infer(node.right)
            if left not in ("int", "float") or right not in ("int", "float"):
                return None
            if isinstance(node.op, ast.Div) or "float" in (left, right):
                return "float"
            if (
                isinstance(node.op, ast.Pow)
                and isinstance(node.right, ast.UnaryOp)
                and isinstance(node.right.op, ast.USub)
            ):
                return "float"
            return "int"
        if isinstance(node, (ast.BoolOp, ast.Compare)):
            return "bool"
        if (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "set" and not node.args and not node.keywords
        ):
            return "set"
        return None

    return infer(expression)


def _compatible(actual: str | None, expected: str) -> bool:
    if actual is None:
        return True
    actual_spec, expected_spec = parse_type(actual), parse_type(expected)
    if expected_spec.name == "union":
        return any(_compatible(actual, format_type(option)) for option in expected_spec.arguments)
    if actual_spec.name == "union":
        return all(
            _compatible(format_type(option), expected)
            for option in actual_spec.arguments
        )
    if actual_spec.name == "int" and expected_spec.name == "float":
        return True
    if actual_spec.name != expected_spec.name:
        return False
    if not expected_spec.arguments:
        return True
    if not actual_spec.arguments:
        return True
    if len(actual_spec.arguments) != len(expected_spec.arguments):
        return False
    return all(
        _compatible(format_type(actual_item), format_type(expected_item))
        and _compatible(format_type(expected_item), format_type(actual_item))
        for actual_item, expected_item in zip(
            actual_spec.arguments, expected_spec.arguments
        )
    )


def _result_type(
    parts: list[str],
    variables: dict[str, str | None],
    functions: dict[str, str | None],
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
    if command == "compare" and len(parts) >= 4:
        return parts[-1], _type_of(" ".join(parts[1:-1]), variables, functions)
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
        function_type = _type_of(parts[2], variables, functions)
        if function_type is not None:
            spec = parse_type(function_type)
            if spec.name == "function":
                return parts[parts.index("->") + 1], format_type(spec.arguments[-1])
        return parts[parts.index("->") + 1], None
    return None


def check_types(lines: list[str]) -> list[tuple[int, str]]:
    """Return (zero-based line, diagnostic) pairs for definite type mismatches."""
    diagnostics: list[tuple[int, str]] = []
    globals_: dict[str, str | None] = {}
    scopes = [globals_]
    record_types: dict[str, dict[str, str]] = {}
    function_types: dict[str, str | None] = {}
    function_parameters: dict[str, list[tuple[str, str | None]]] = {}
    function_returns: list[str | None] = []
    function_depth = 0

    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parts = list(tokenize_line(stripped))
        except SyntaxError:
            continue
        if not parts:
            continue
        if _FUNCTION.match(stripped):
            function_depth += 1
            scopes.append(dict(globals_))
            declarations = parts[3:]
            return_type = None
            if "->" in declarations:
                return_index = declarations.index("->")
                return_type = " ".join(declarations[return_index + 1:])
                declarations = declarations[:return_index]
            normalized_return_type = None
            if return_type:
                try:
                    return_spec = parse_type(return_type)
                    if is_known_type(return_spec, set(record_types)):
                        normalized_return_type = format_type(return_spec)
                except ValueError:
                    pass
            function_returns.append(normalized_return_type)
            parameter_types = []
            named_parameter_types = []
            for declaration in declarations:
                parameter = declaration.lstrip("*").partition("=")[0]
                name, separator, annotation = parameter.partition(":")
                if separator:
                    try:
                        spec = parse_type(annotation)
                        scopes[-1][name] = (
                            format_type(spec)
                            if is_known_type(spec, set(record_types))
                            else None
                        )
                        parameter_types.append(format_type(spec))
                        named_parameter_types.append((name, format_type(spec)))
                    except ValueError:
                        scopes[-1][name] = None
                        parameter_types.append(None)
                        named_parameter_types.append((name, None))
                else:
                    scopes[-1][name] = None
                    parameter_types.append(None)
                    named_parameter_types.append((name, None))
            function_parameters[parts[2]] = named_parameter_types
            if (
                return_type
                and all(parameter_types)
                and all(not declaration.startswith("*") for declaration in declarations)
            ):
                try:
                    function_spec = parse_type(
                        f"({', '.join(parameter_types)}) -> {normalized_return_type}"
                    )
                    if is_known_type(function_spec, set(record_types)):
                        function_types[parts[2]] = format_type(function_spec)
                    else:
                        function_types[parts[2]] = None
                except ValueError:
                    function_types[parts[2]] = None
            else:
                function_types[parts[2]] = None
            continue
        if parts[0] == "endfunc" and function_depth:
            scopes.pop()
            function_depth -= 1
            function_returns.pop()
            continue
        variables = scopes[-1]
        if parts[0] == "record" and len(parts) >= 3 and parts[1] == "define":
            fields = {}
            for declaration in parts[3:]:
                if declaration.count(":") == 1:
                    field_name, field_type = declaration.split(":", 1)
                    try:
                        spec = parse_type(field_type)
                    except ValueError:
                        continue
                    if is_known_type(spec, set(record_types)):
                        fields[field_name] = format_type(spec)
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
                    actual = _type_of(token, variables, function_types)
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
            and parts[2].endswith(":") and "=" in parts
        ):
            equal_index = parts.index("=")
            name = parts[2][:-1]
            declared = " ".join(parts[3:equal_index])
            try:
                declared_spec = parse_type(declared)
            except ValueError:
                continue
            if not is_known_type(declared_spec, set(record_types)):
                continue
            declared = format_type(declared_spec)
            actual = _type_of(
                " ".join(parts[equal_index + 1:]), variables, function_types
            )
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
                condition_type = _type_of(parts[1], variables, function_types)
                if condition_type is not None and condition_type != "bool":
                    diagnostics.append((
                        line_number,
                        f"Type mismatch: assert condition has type '{condition_type}', "
                        "expected 'bool'.",
                    ))
            if len(parts) == 3:
                message_type = _type_of(parts[2], variables, function_types)
                if message_type is not None and message_type != "string":
                    diagnostics.append((
                        line_number,
                        f"Type mismatch: assert message has type '{message_type}', "
                        "expected 'string'.",
                    ))
            continue
        if parts[0] in ("if", "elseif") and len(parts) > 1:
            actual = _type_of(" ".join(parts[1:]), variables, function_types)
            if actual is not None and actual != "bool":
                diagnostics.append((
                    line_number,
                    f"Type mismatch: condition has type '{actual}', expected 'bool'.",
                ))
        if (
            parts[0] == "loop" and len(parts) > 2 and parts[1] == "while"
        ):
            actual = _type_of(" ".join(parts[2:]), variables, function_types)
            if actual is not None and actual != "bool":
                diagnostics.append((
                    line_number,
                    f"Type mismatch: loop condition has type '{actual}', expected 'bool'.",
                ))
        if parts[0] == "set" and len(parts) >= 4 and parts[2] == "=":
            destination = parts[1]
            expected = variables.get(destination)
            actual = _type_of(" ".join(parts[3:]), variables, function_types)
            if actual is not None and expected is not None and not _compatible(actual, expected):
                diagnostics.append((
                    line_number,
                    f"Type mismatch: assignment has type '{actual}' but variable "
                    f"'{destination}' has type '{expected}'.",
                ))
            continue
        if parts[0] == "return" and function_returns:
            expected = function_returns[-1]
            actual = _type_of(
                " ".join(parts[1:]) if len(parts) > 1 else "none",
                variables,
                function_types,
            )
            if (
                expected is not None and actual is not None
                and not _compatible(actual, expected)
            ):
                diagnostics.append((
                    line_number,
                    f"Type mismatch: function return has type '{actual}' "
                    f"but annotation requires '{expected}'.",
                ))
            continue
        if len(parts) >= 3 and parts[:2] == ["func", "call"]:
            function_type = _type_of(parts[2], variables, function_types)
            if function_type is not None:
                spec = parse_type(function_type)
                if spec.name == "function":
                    call_arguments = parts[3:]
                    if "->" in call_arguments:
                        call_arguments = call_arguments[:call_arguments.index("->")]
                    named_parameters = function_parameters.get(parts[2], [])
                    for argument_index, argument in enumerate(call_arguments):
                        parameter_name, separator, value = argument.partition("=")
                        if separator and parameter_name.isidentifier():
                            matching = next(
                                (
                                    parameter_type for name, parameter_type in named_parameters
                                    if name == parameter_name
                                ),
                                None,
                            )
                            if matching is None:
                                continue
                            expected_argument = matching
                        else:
                            if argument_index >= len(spec.arguments) - 1:
                                continue
                            expected_argument = format_type(spec.arguments[argument_index])
                            value = argument
                        actual_argument = _type_of(value, variables, function_types)
                        if (
                            actual_argument is not None
                            and not _compatible(actual_argument, expected_argument)
                        ):
                            diagnostics.append((
                                line_number,
                                f"Type mismatch: argument '{value}' has type "
                                f"'{actual_argument}' but parameter requires "
                                f"'{expected_argument}'.",
                            ))

        result = _result_type(parts, variables, function_types)
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
