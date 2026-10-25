from io import IOBase

from .expressions import evaluate_expression
from .runtime import Runtime
from .string_builtins import resolve


def execute_io_command(parts: list[str], runtime: Runtime) -> None:
    if parts[0] == "text":
        if len(parts) < 3:
            raise SyntaxError("Usage: text <input/output> <value>")
        action = parts[1]
        if action == "output":
            value = " ".join(parts[2:])
            try:
                result = evaluate_expression(value, runtime)
            except SyntaxError:
                if any(operator in value for operator in ("+", "-", "*", "/", "%", "(", ")", "<", ">", "==", "!=")):
                    raise
                result = resolve(value, runtime)
            print(result)
            return
        if action == "input" and len(parts) == 3:
            variable = runtime.require_var(parts[2])
            if variable["type"] != "string":
                raise TypeError(f"Variable '{parts[2]}' must be a string for text input.")
            runtime.assign_var(parts[2], input())
            return
        raise SyntaxError("Usage: text <input/output> <value>")

    if parts[0] == "open" and len(parts) == 4:
        path, mode, destination = (resolve(parts[1], runtime), resolve(parts[2], runtime), parts[3])
        if not isinstance(path, str) or not isinstance(mode, str):
            raise TypeError("open() path and mode must be strings.")
        existing = runtime.get_var(destination)
        if existing is not None and existing["type"] != "file":
            raise TypeError(f"Variable '{destination}' must be a file destination.")
        file_obj = open(path, mode, encoding=None if "b" in mode else "utf-8")
        runtime.register_file(file_obj)
        if existing is None:
            runtime.define_var(destination, "file", file_obj)
        else:
            runtime.assign_var(destination, file_obj)
        return

    if parts[0] == "close" and len(parts) == 2:
        variable = runtime.require_var(parts[1])
        if variable["type"] != "file" or not isinstance(variable["value"], IOBase):
            raise TypeError(f"Variable '{parts[1]}' must be an open file.")
        runtime.close_file(variable["value"])
        return

    if parts[0] == "file":
        if len(parts) != 4 or parts[1] not in ("read", "write"):
            raise SyntaxError(
                "Usage: file read <file_variable> <destination> or "
                "file write <file_variable> <value>"
            )
        file_variable = runtime.require_var(parts[2])
        file_obj = file_variable["value"]
        if file_variable["type"] != "file" or not isinstance(file_obj, IOBase):
            raise TypeError(f"Variable '{parts[2]}' is not a file.")
        if file_obj.closed:
            raise ValueError(f"File '{parts[2]}' is closed.")
        binary = "b" in file_obj.mode
        if parts[1] == "read":
            destination = runtime.require_var(parts[3])
            expected_type = "bytes" if binary else "string"
            if destination["type"] != expected_type and not (
                binary and destination["type"] == "bytearray"
            ):
                raise TypeError(
                    f"Reading this file requires a '{expected_type}' destination."
                )
            content = file_obj.read()
            if destination["type"] == "bytearray":
                content = bytearray(content)
            runtime.assign_var(parts[3], content)
        else:
            content = resolve(parts[3], runtime)
            if binary:
                if not isinstance(content, (bytes, bytearray)):
                    raise TypeError("Binary files require a bytes or bytearray value.")
            elif not isinstance(content, str):
                raise TypeError("Text files require a string value.")
            file_obj.write(content)
        return

    raise SyntaxError(f"Invalid {parts[0]} command or arguments.")
