import operator
from typing import Any, Callable

from . import arith, iteration, string_builtins, utilities
from .collection_commands import execute_collection_command
from .conversion import convert_value, parse_value
from .ffi import execute_ffi
from .io_commands import execute_io_command
from .runtime import Runtime, TYPES
from .string_builtins import resolve


def _assign(runtime: Runtime, name: str, value: Any) -> None:
    target = runtime.require_var(name)
    runtime.update_var(name, target["type"], value)


def _comparison_value(value: str, runtime: Runtime) -> Any:
    if runtime.get_var(value) is not None:
        return runtime.require_var(value)["value"]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def evaluate_condition(condition: str, runtime: Runtime) -> bool:
    condition = condition.strip()
    if condition.lower() in ("true", "false"):
        return condition.lower() == "true"
    variable = runtime.get_var(condition)
    return bool(variable["value"]) if variable else False


def _builtin_callable(name: str, value: Any) -> Any:
    if name == "abs":
        return abs(value)
    if name == "bool":
        return bool(value)
    if name == "chr":
        return string_builtins.character(value)
    if name == "int":
        return convert_value(value, "int")
    if name == "float":
        return convert_value(value, "float")
    if name == "str":
        return convert_value(value, "string")
    if name == "ord":
        return string_builtins.ordinal(value)
    if name == "round":
        return round(value)
    if name == "ascii":
        return string_builtins.ascii_value(value)
    if name == "repr":
        return string_builtins.representation(value)
    if name == "len":
        return utilities.length(value)
    raise ValueError(f"Unknown built-in callable: {name}")


def execute_command(
    parts: list[str],
    runtime: Runtime,
    invoke_function: Callable[[str, list[Any]], Any],
    source_name: str = "<memory>",
) -> None:
    command = parts[0]

    if command == "ffi":
        execute_ffi(parts, runtime, source_name)
        return

    if command == "define":
        if len(parts) < 6 or parts[1] != "var" or not parts[2].endswith(":") or parts[4] != "=":
            raise SyntaxError("Usage: define var <name>: <type> = <value>")
        name, value_type = parts[2][:-1], parts[3]
        if value_type not in TYPES:
            raise ValueError(f"Unknown type: {value_type}")
        value = parse_value(" ".join(parts[5:]), value_type, runtime)
        runtime.define_var(name, value_type, value)
        return

    if command == "convert":
        if len(parts) == 4 and parts[2] == "to":
            name, target_type = parts[1], parts[3]
        elif len(parts) == 3:
            name, target_type = parts[1], parts[2]
        else:
            raise SyntaxError("Usage: convert <variable> to <type>")
        variable = runtime.require_var(name)
        try:
            converted = convert_value(variable["value"], target_type)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Cannot convert '{name}' to {target_type}: {error}") from error
        runtime.update_var(name, target_type, converted)
        return

    if command == "arith":
        single_ops = {"abs", "round", "sum", "bin", "hex", "oct"}
        if len(parts) == 3 and parts[1] in single_ops | {"max", "min"}:
            result = arith.arith(parts[1], parts[2], None, runtime)
        elif len(parts) == 4 and parts[1] not in single_ops:
            result = arith.arith(parts[1], parts[2], parts[3], runtime)
        else:
            raise SyntaxError(
                "Usage: arith <abs|round|sum|bin|hex|oct> <value> "
                "OR arith <operation> <value1> <value2>"
            )
        print(result)
        return

    if command == "compare":
        if len(parts) != 5:
            raise SyntaxError("Usage: compare <value1> <op> <value2> <dest_bool_var>")
        operations = {
            "==": operator.eq, "!=": operator.ne, "<": operator.lt,
            ">": operator.gt, "<=": operator.le, ">=": operator.ge,
        }
        destination = runtime.require_var(parts[4])
        if destination["type"] != "bool":
            raise TypeError(f"Destination variable '{parts[4]}' must be a defined boolean.")
        if parts[2] not in operations:
            raise SyntaxError(f"Unknown comparison operator: {parts[2]}")
        result = operations[parts[2]](
            _comparison_value(parts[1], runtime), _comparison_value(parts[3], runtime)
        )
        runtime.update_var(parts[4], "bool", result)
        return

    if command in ("list", "dict", "set", "tuple"):
        execute_collection_command(parts, runtime)
        return

    if command in ("text", "open"):
        execute_io_command(parts, runtime)
        return

    if command in ("getattr", "hasattr", "setattr"):
        _execute_attribute_command(parts, runtime)
        return

    if command in ("bytes", "bytearray"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <value_or_var> <dest_var>")
        value = resolve(parts[1], runtime)
        result = value if isinstance(value, TYPES[command]) else str(value).encode("utf-8")
        if command == "bytearray":
            result = bytearray(result)
        _assign(runtime, parts[2], result)
        return

    if command in ("all", "any"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <collection> <dest_bool_var>")
        collection = runtime.require_var(parts[1])
        if collection["type"] not in ("list", "tuple", "set", "dict"):
            raise TypeError(f"Variable '{parts[1]}' must be a defined collection.")
        _assign(
            runtime, parts[2],
            utilities.all_values(collection["value"]) if command == "all"
            else utilities.any_values(collection["value"]),
        )
        return

    if command in ("ascii", "repr"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <value_or_var> <dest_string_var>")
        value = resolve(parts[1], runtime)
        result = (
            string_builtins.ascii_value(value) if command == "ascii"
            else string_builtins.representation(value)
        )
        _assign(runtime, parts[2], result)
        return

    if command == "chr":
        if len(parts) != 3:
            raise SyntaxError("Usage: chr <integer_or_var> <dest_string_var>")
        _assign(runtime, parts[2], string_builtins.character(resolve(parts[1], runtime)))
        return

    if command == "ord":
        if len(parts) != 3:
            raise SyntaxError("Usage: ord <character_or_var> <dest_int_var>")
        _assign(runtime, parts[2], string_builtins.ordinal(resolve(parts[1], runtime)))
        return

    if command == "format":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: format <value_or_var> <format_spec> <dest_string_var>")
        value, spec, destination = resolve(parts[1], runtime), parts[2], parts[-1]
        if len(parts) == 3:
            value, spec, destination = resolve(parts[1], runtime), "", parts[2]
        else:
            spec = resolve(spec, runtime)
        _assign(runtime, destination, string_builtins.format_value(value, str(spec)))
        return

    if command == "enumerate":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: enumerate <iterable> <dest_list> [start]")
        values = resolve(parts[1], runtime)
        start = int(resolve(parts[3], runtime)) if len(parts) == 4 else 0
        _assign(runtime, parts[2], iteration.enumerate_values(values, start))
        return

    if command in ("map", "filter"):
        if len(parts) != 4:
            raise SyntaxError(f"Usage: {command} <function> <iterable> <dest_list>")
        function_name, iterable, destination = parts[1], resolve(parts[2], runtime), parts[3]

        def callback(value: Any) -> Any:
            if runtime.resolve_function(function_name) is not None:
                result = invoke_function(function_name, [value])
                if result is None:
                    raise ValueError(
                        f"Function '{function_name}' must return a value when used by {command}."
                    )
                return result
            return _builtin_callable(function_name, value)

        result = (
            iteration.map_values(callback, iterable) if command == "map"
            else iteration.filter_values(callback, iterable)
        )
        _assign(runtime, destination, result)
        return

    if command == "iter":
        if len(parts) != 3:
            raise SyntaxError("Usage: iter <iterable> <dest_iterator_var>")
        iterator_value = iter(resolve(parts[1], runtime))
        if runtime.get_var(parts[2]) is None:
            runtime.define_var(parts[2], "iterator", iterator_value)
        else:
            _assign(runtime, parts[2], iterator_value)
        return

    if command == "next":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: next <iterator> <destination> [default]")
        iterator_value = runtime.require_var(parts[1])
        if iterator_value["type"] != "iterator":
            raise TypeError(f"Variable '{parts[1]}' is not an iterator.")
        default = resolve(parts[3], runtime) if len(parts) == 4 else ...
        try:
            result = next(iterator_value["value"]) if default is ... else next(iterator_value["value"], default)
        except StopIteration as error:
            raise ValueError("next() called on an exhausted iterator.") from error
        _assign(runtime, parts[2], result)
        return

    if command == "range":
        if len(parts) not in (3, 4, 5):
            raise SyntaxError("Usage: range <stop> <dest_list> OR range <start> <stop> <dest_list> [step]")
        if len(parts) == 3:
            start, stop, step, destination = 0, int(resolve(parts[1], runtime)), 1, parts[2]
        elif len(parts) == 4:
            start, stop, step, destination = (
                int(resolve(parts[1], runtime)), int(resolve(parts[2], runtime)), 1, parts[3]
            )
        else:
            start, stop, step, destination = (
                int(resolve(parts[1], runtime)), int(resolve(parts[2], runtime)),
                int(resolve(parts[4], runtime)), parts[3],
            )
        if step == 0:
            raise ValueError("range() arg 3 must not be zero.")
        _assign(runtime, destination, list(range(start, stop, step)))
        return

    if command == "reversed":
        if len(parts) != 3:
            raise SyntaxError("Usage: reversed <iterable> <dest_list>")
        _assign(runtime, parts[2], iteration.reversed_values(resolve(parts[1], runtime)))
        return

    if command == "slice":
        if len(parts) not in (5, 6):
            raise SyntaxError("Usage: slice <iterable> <start> <stop> <dest> [step]")
        source = runtime.require_var(parts[1])
        start, stop = int(resolve(parts[2], runtime)), int(resolve(parts[3], runtime))
        step = int(resolve(parts[5], runtime)) if len(parts) == 6 else None
        result = iteration.slice_values(source["value"], start, stop, step)
        destination = parts[4]
        target = runtime.require_var(destination)
        runtime.update_var(destination, target["type"], result)
        return

    if command == "sorted":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: sorted <iterable> <dest_list> [reverse]")
        reverse = resolve(parts[3], runtime) if len(parts) == 4 else False
        if not isinstance(reverse, bool):
            raise TypeError("sorted() reverse option must be boolean.")
        _assign(runtime, parts[2], iteration.sorted_values(resolve(parts[1], runtime), reverse))
        return

    if command == "zip":
        if len(parts) < 4:
            raise SyntaxError("Usage: zip <iterable1> <iterable2> [...] <dest_list>")
        values = [resolve(name, runtime) for name in parts[1:-1]]
        _assign(runtime, parts[-1], iteration.zip_values(*values))
        return

    if command in ("bool", "callable", "id", "len", "type", "vars", "wait"):
        _execute_utility_command(parts, runtime)
        return

    raise SyntaxError(f"Unknown command: {command}")


def _execute_attribute_command(parts: list[str], runtime: Runtime) -> None:
    command = parts[0]
    if len(parts) != 4:
        raise SyntaxError(f"Usage: {command} <variable> <attribute> <destination>")
    obj_name, attr_name, destination = parts[1], resolve(parts[2], runtime), parts[3]
    variable = runtime.require_var(obj_name)
    obj = variable["value"]
    if command == "getattr":
        value = obj[attr_name] if isinstance(obj, dict) else getattr(obj, attr_name)
        target = runtime.require_var(destination)
        runtime.update_var(destination, target["type"], value)
    elif command == "hasattr":
        _assign(runtime, destination, attr_name in obj if isinstance(obj, dict) else hasattr(obj, attr_name))
    else:
        value = resolve(parts[3], runtime)
        if isinstance(obj, dict):
            obj[attr_name] = value
        else:
            setattr(obj, attr_name, value)


def _execute_utility_command(parts: list[str], runtime: Runtime) -> None:
    command = parts[0]
    if command == "bool" and len(parts) == 3:
        _assign(runtime, parts[2], bool(resolve(parts[1], runtime)))
    elif command == "callable" and len(parts) == 3:
        result = runtime.resolve_function(parts[1]) is not None or parts[1] in {
            "abs", "ascii", "bool", "chr", "float", "int", "len", "ord",
            "repr", "round", "str",
        }
        _assign(runtime, parts[2], result)
    elif command == "id" and len(parts) == 3:
        _assign(runtime, parts[2], id(runtime.require_var(parts[1])["value"]))
    elif command == "len" and len(parts) == 3:
        _assign(runtime, parts[2], utilities.length(runtime.require_var(parts[1])["value"]))
    elif command == "type" and len(parts) == 3:
        variable = runtime.require_var(parts[1])
        _assign(runtime, parts[2], utilities.type_name(variable["value"], variable["type"]))
    elif command == "vars" and len(parts) == 1:
        merged = {}
        for scope in runtime.scopes:
            merged.update(scope)
        print("--- Active Scope Variables ---")
        for name, variable in merged.items():
            print(f"{name}: {variable['type']} = {variable['value']}")
        print("--- Defined Functions ---")
        for name in runtime.functions:
            print(f"func {name}")
    elif command == "wait" and len(parts) == 2:
        import time
        time.sleep(float(resolve(parts[1], runtime)))
    else:
        raise SyntaxError(f"Invalid {command} command or arguments.")
