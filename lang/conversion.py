import ast
from typing import Any

from .runtime import TYPES, Runtime
from .type_system import FunctionReference, format_type, parse_type


def _literal(value: str, runtime: Runtime) -> Any:
    normalized = []
    quote = None
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if quote is not None:
            normalized.append(char)
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
            normalized.append(char)
            index += 1
            continue
        matched = False
        for language_value, python_value in (("true", "True"), ("false", "False")):
            end = index + len(language_value)
            if value[index:end].lower() == language_value:
                before = value[index - 1] if index else ""
                after = value[end] if end < len(value) else ""
                if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                    normalized.append(python_value)
                    index = end
                    matched = True
                    break
        if not matched:
            normalized.append(char)
            index += 1
    expression = ast.parse("".join(normalized), mode="eval").body

    def evaluate(node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "none":
                return None
            variable = runtime.get_var(node.id)
            if variable is None:
                raise ValueError(f"Variable '{node.id}' is not defined.")
            return variable["value"]
        if isinstance(node, ast.List):
            return [evaluate(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(evaluate(item) for item in node.elts)
        if isinstance(node, ast.Set):
            return {evaluate(item) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {evaluate(key): evaluate(item) for key, item in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            number = evaluate(node.operand)
            if not isinstance(number, (int, float)) or isinstance(number, bool):
                raise ValueError("Unary signs can only be used with numeric literals.")
            return number if isinstance(node.op, ast.UAdd) else -number
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "set" and not node.args:
            return set()
        raise ValueError("Unsupported value in literal.")

    return evaluate(expression)


def parse_value(value: str, expected_type: str, runtime: Runtime) -> Any:
    spec = parse_type(expected_type)
    expected_type = format_type(spec)
    if not runtime.type_is_known(expected_type):
        raise ValueError(f"Unknown type: {expected_type}")

    data = runtime.get_var(value)
    quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"')

    if spec.name == "function":
        if data is not None and isinstance(data["value"], FunctionReference):
            function = data["value"]
        else:
            resolved = runtime.resolve_function(value)
            if resolved is None:
                raise ValueError(f"Function '{value}' is not defined.")
            function = FunctionReference(resolved)
        if not runtime.value_matches_type(expected_type, function):
            raise TypeError(
                f"Function '{value}' does not match type '{expected_type}'."
            )
        return function

    if spec.name == "union":
        if value.lower() == "none":
            candidate = None
        elif data is not None:
            candidate = data["value"]
        else:
            function_name = runtime.resolve_function(value)
            candidate = (
                FunctionReference(function_name)
                if function_name is not None
                else _literal(value, runtime)
            )
        if runtime.value_matches_type(expected_type, candidate):
            return candidate
        raise TypeError(f"Value does not match type '{expected_type}'.")

    if spec.arguments:
        if data is not None:
            candidate = data["value"]
            if spec.name in ("list", "dict", "set", "tuple"):
                candidate = TYPES[spec.name](candidate)
        elif value.lower() == "none":
            candidate = None
        else:
            candidate = _literal(value, runtime)
        if not runtime.value_matches_type(expected_type, candidate):
            raise TypeError(f"Value does not match type '{expected_type}'.")
        return candidate

    if expected_type == "none":
        if value.lower() == "none":
            return None
        raise ValueError("Expected 'none'.")

    if expected_type == "string":
        if quoted:
            return _literal(value, runtime)
        if data is not None and isinstance(data["value"], str):
            return data["value"]
        raise ValueError("Expected a quoted string or string variable.")

    if expected_type == "bool":
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        if data is not None and isinstance(data["value"], bool):
            return data["value"]
        raise ValueError("Expected 'true', 'false', or a boolean variable.")

    if expected_type in ("list", "tuple", "set", "dict"):
        if data is not None:
            if not isinstance(data["value"], TYPES[expected_type]):
                raise TypeError(f"Variable '{value}' is not a {expected_type}.")
            return TYPES[expected_type](data["value"])
        try:
            parsed = _literal(value, runtime)
        except (ValueError, SyntaxError) as error:
            raise ValueError(f"Expected a {expected_type} literal or variable.") from error
        if not isinstance(parsed, TYPES[expected_type]):
            raise TypeError(f"Expected a {expected_type} literal.")
        return parsed

    if expected_type in ("bytes", "bytearray"):
        if data is not None:
            raw = data["value"]
            if isinstance(raw, (bytes, bytearray)):
                return TYPES[expected_type](raw)
            return TYPES[expected_type](str(raw).encode("utf-8"))
        raw = _literal(value, runtime) if quoted else value
        if isinstance(raw, int):
            return TYPES[expected_type](raw)
        if isinstance(raw, str):
            return TYPES[expected_type](raw.encode("utf-8"))
        return TYPES[expected_type](raw)

    if expected_type in ("int", "float"):
        if data is not None:
            if data["type"] != expected_type:
                raise TypeError(
                    f"Variable '{value}' is type '{data['type']}', not '{expected_type}'."
                )
            return data["value"]
        try:
            return TYPES[expected_type](value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"'{value}' is not a valid {expected_type}.") from error

    if expected_type in ("file", "iterator") and data is not None:
        if data["type"] != expected_type:
            raise TypeError(f"Variable '{value}' is not a {expected_type}.")
        return data["value"]
    raise ValueError(f"Unable to parse value '{value}' for type '{expected_type}'.")


def convert_value(value: Any, target_type: str) -> Any:
    if target_type not in TYPES:
        raise ValueError(f"Unknown type: {target_type}")
    if target_type == "none":
        if value is None:
            return None
        raise TypeError("Only none can be converted to none.")
    if target_type == "bool" and isinstance(value, str):
        if value.lower() not in ("true", "false"):
            raise ValueError("String must be 'true' or 'false'.")
        return value.lower() == "true"
    if target_type == "string" and isinstance(value, bool):
        return "true" if value else "false"
    if target_type == "int":
        return int(float(value)) if isinstance(value, (str, float)) else int(value)
    if target_type == "list":
        return list(value) if isinstance(value, (str, tuple, set, dict)) else [value]
    if target_type == "tuple":
        return tuple(value) if isinstance(value, (str, list, set, dict)) else (value,)
    if target_type == "set":
        return set(value) if isinstance(value, (str, list, tuple, dict)) else {value}
    if target_type == "bytes":
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    if target_type == "bytearray":
        return value if isinstance(value, bytearray) else bytearray(str(value).encode("utf-8"))
    if target_type in ("iterator", "file"):
        if target_type == "file" and hasattr(value, "read"):
            return value
        if target_type == "iterator":
            return iter(value)
        raise TypeError("Only an open file can be converted to file.")
    return TYPES[target_type](value)
