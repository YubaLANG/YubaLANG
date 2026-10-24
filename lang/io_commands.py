from io import IOBase

from .runtime import Runtime
from .string_builtins import resolve


def execute_io_command(parts: list[str], runtime: Runtime) -> None:
    if parts[0] == "text":
        if len(parts) < 3:
            raise SyntaxError("Usage: text <input/output> <value>")
        action = parts[1]
        if action == "output":
            value = " ".join(parts[2:])
            if len(parts) == 3:
                token = parts[2]
                quoted = len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"')
                is_boolean = token.lower() in ("true", "false")
                try:
                    float(token)
                    is_number = True
                except ValueError:
                    is_number = False
                if not quoted and not is_boolean and not is_number and runtime.get_var(token) is None:
                    raise ValueError(f"Variable '{token}' is not defined.")
            print(resolve(value, runtime))
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

    raise SyntaxError(f"Invalid {parts[0]} command or arguments.")
