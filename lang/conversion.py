from typing import Any

from .runtime import TYPES, Runtime
from .expressions import evaluate_expression
from .type_system import FunctionReference, format_type, parse_type


def _literal(value: str, runtime: Runtime) -> Any:
    return evaluate_expression(value, runtime)


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
            if (
                spec.name in ("list", "dict", "set", "tuple")
                and not isinstance(candidate, TYPES[spec.name])
            ):
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
        result = evaluate_expression(value, runtime)
        if isinstance(result, bool):
            return result
        raise ValueError("Expected 'true', 'false', or a boolean variable.")

    if expected_type in ("list", "tuple", "set", "dict"):
        if data is not None:
            if not isinstance(data["value"], TYPES[expected_type]):
                raise TypeError(f"Variable '{value}' is not a {expected_type}.")
            return data["value"]
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
                if isinstance(raw, TYPES[expected_type]):
                    return raw
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
        result = evaluate_expression(value, runtime)
        if expected_type == "float" and isinstance(result, int) and not isinstance(result, bool):
            return float(result)
        if not isinstance(result, TYPES[expected_type]) or isinstance(result, bool):
            raise TypeError(f"Expected a {expected_type} expression.")
        return result

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
