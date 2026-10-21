"""A narrow ctypes bridge for calling local C ABI functions."""

import ctypes
import math
from pathlib import Path
from typing import Any

from .runtime import Runtime
from .string_builtins import resolve


_C_TYPES = {
    "i32": (ctypes.c_int32, "int"),
    "i64": (ctypes.c_int64, "int"),
    "f64": (ctypes.c_double, "float"),
    "bool": (ctypes.c_bool, "bool"),
}
_RETURN_TYPES = {**_C_TYPES, "void": (None, None)}


def _library_path(value: str, source_name: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        source_path = Path(source_name)
        base_directory = source_path.resolve().parent if source_name != "<memory>" else Path.cwd()
        path = base_directory / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"C library file '{path}' does not exist.")
    return path


def _load_library(path: Path, runtime: Runtime) -> Any:
    key = str(path)
    if key not in runtime.native_libraries:
        try:
            runtime.native_libraries[key] = ctypes.CDLL(key)
        except OSError as error:
            raise ValueError(f"Cannot load C library '{path}': {error}") from error
    return runtime.native_libraries[key]


def _argument_value(type_name: str, value_token: str, runtime: Runtime) -> Any:
    if type_name not in _C_TYPES:
        raise ValueError(
            f"Unsupported C argument type '{type_name}'. Use i32, i64, f64, or bool."
        )

    value = resolve(value_token, runtime)
    c_type, expected_type = _C_TYPES[type_name]
    if expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"C {type_name} arguments require an integer.")
        limits = {
            "i32": (-(2**31), 2**31 - 1),
            "i64": (-(2**63), 2**63 - 1),
        }
        lower, upper = limits[type_name]
        if not lower <= value <= upper:
            raise ValueError(f"Value is outside the range of C {type_name}.")
    elif expected_type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("C f64 arguments require a number.")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("C f64 arguments must be finite.")
    elif not isinstance(value, bool):
        raise TypeError("C bool arguments require true, false, or a bool variable.")
    return c_type, value


def execute_ffi(parts: list[str], runtime: Runtime, source_name: str) -> None:
    if len(parts) < 5 or parts[1] != "call":
        raise SyntaxError(
            "Usage: ffi call <library> <symbol> <return-type> "
            "[<argument-type> <value> ...] [-> <destination>]"
        )

    arguments = parts[5:]
    destination = None
    if "->" in arguments:
        arrow = arguments.index("->")
        if arrow != len(arguments) - 2:
            raise SyntaxError("C return destination must follow '->'.")
        destination = arguments[-1]
        arguments = arguments[:arrow]
    if len(arguments) % 2:
        raise SyntaxError("C arguments must be provided as type/value pairs.")

    return_type = parts[4]
    if return_type not in _RETURN_TYPES:
        raise ValueError(
            f"Unsupported C return type '{return_type}'. "
            "Use i32, i64, f64, bool, or void."
        )
    c_return_type, destination_type = _RETURN_TYPES[return_type]
    if (return_type == "void") != (destination is None):
        if return_type == "void":
            raise SyntaxError("C void functions do not have a return destination.")
        raise SyntaxError("Non-void C functions require '-> <destination>'.")

    if destination is not None:
        target = runtime.require_var(destination)
        if target["type"] != destination_type:
            raise TypeError(
                f"C {return_type} result requires a YubaLANG {destination_type} "
                f"destination, not '{target['type']}'."
            )

    c_argument_types = []
    argument_values = []
    for type_name, value_token in zip(arguments[::2], arguments[1::2]):
        c_type, value = _argument_value(type_name, value_token, runtime)
        c_argument_types.append(c_type)
        argument_values.append(value)

    library_name = resolve(parts[2], runtime)
    if not isinstance(library_name, str):
        raise TypeError("C library path must be a string.")
    library_path = _library_path(library_name, source_name)
    library = _load_library(library_path, runtime)
    try:
        function = getattr(library, parts[3])
    except AttributeError as error:
        raise ValueError(
            f"C function '{parts[3]}' was not found in '{library_path}'."
        ) from error
    function.argtypes = c_argument_types
    function.restype = c_return_type
    try:
        result = function(*argument_values)
    except (ctypes.ArgumentError, OSError, TypeError, ValueError) as error:
        raise ValueError(f"C function '{parts[3]}' failed: {error}") from error

    if destination is not None:
        runtime.update_var(destination, destination_type, result)
